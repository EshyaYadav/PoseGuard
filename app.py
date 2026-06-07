from flask import Flask, render_template, request, redirect, url_for, session, Response, abort
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import cv2
from playsound import playsound
from werkzeug.utils import secure_filename
import os
import tempfile
import time
from datetime import datetime
from collections import deque
from threading import Thread, Event
from dotenv import load_dotenv
from pymongo import MongoClient
import gridfs
from bson.objectid import ObjectId
from pose_detection import detect_pose

# Load environment variables
load_dotenv()

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
mongo_db = client["driver_safety"]
collection = mongo_db["records"]
fs = gridfs.GridFS(mongo_db)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")
# For Vercel, allow camera to fail gracefully if it doesn't exist
camera = cv2.VideoCapture(0)
if not camera.isOpened():
    print("Warning: Camera not found (expected on serverless environments like Vercel)")

def map_status(class_name):
    mapping = {
        "Normal Pose": "Safe",
        "Phone (Using)": "Phone",
        "Phone (Talking)": "Phone",
        "Looking Away": "Drowsy",
        "Distracted....": "Drowsy",
        "Drinking": "Unsafe",
        "Makeup": "Unsafe",
        "No Hands on Wheel": "Unsafe"
    }
    return mapping.get(class_name, "Unsafe")

# Sound control
sound_stop_event = Event()

# Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'processed')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv'}

db = SQLAlchemy(app)

# Create folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ===================== MODELS =====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def __init__(self, name, username, email, password):
        self.name = name
        self.username = username
        self.email = email
        self.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password.encode())


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(100))
    user_email = db.Column(db.String(120))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ScreenshotAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(200))
    user_email = db.Column(db.String(120))
    alert_type = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class IncidentVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_path = db.Column(db.String(200))
    user_email = db.Column(db.String(120))
    alert_type = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


# ===================== HELPERS =====================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def play_alert_sound(class_name):
    try:
        sound_stop_event.clear()
        import pyttsx3
        engine = pyttsx3.init()
        message = f"Warning: {class_name} detected. Please stay alert, especially in high traffic zones or crowded areas."
        while not sound_stop_event.is_set():
            engine.say(message)
            engine.runAndWait()
            sound_stop_event.wait(1.0)
    except Exception as e:
        print("Sound error:", e)

def save_incident_video(frames, video_filename):
    if not frames:
        return
        
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, video_filename)
    
    height, width, layers = frames[0].shape
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_path, fourcc, 10.0, (width, height))
    for f in frames:
        out.write(f)
    out.release()
    
    try:
        with open(temp_path, 'rb') as video_file:
            fs.put(video_file, filename=video_filename, content_type="video/mp4")
    except Exception as e:
        print("GridFS Video Error:", e)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


# ===================== VIDEO =====================

def gen_frames(user_email):
    unwanted_count = 0
    threshold = 10
    sound_thread = None
    frame_buffer = deque(maxlen=150)
    last_recording_time = 0
    was_unsafe = False

    while True:
        success, frame = camera.read()
        if not success:
            continue

        frame_buffer.append(frame.copy())
        is_unwanted, class_name, confidence = detect_pose(frame)
        
        # Log "Safe" transition
        if not is_unwanted and was_unsafe:
            try:
                collection.insert_one({
                    "event": "Resumed Normal Driving",
                    "confidence": float(confidence),
                    "status": "Safe",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "video_file": None
                })
                was_unsafe = False
            except Exception as e:
                print("Safe Log Error:", e)

        label = f"{class_name}: {confidence*100:.1f}%"
        color = (0,0,255) if is_unwanted else (0,255,0)
        cv2.putText(frame, label, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

        if is_unwanted:
            unwanted_count += 1
        else:
            unwanted_count = 0
            sound_stop_event.set()

        if unwanted_count > threshold:
            filename = f"{user_email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            
            # Encode image to memory and push to GridFS
            try:
                ret_img, buffer_img = cv2.imencode('.jpg', frame)
                if ret_img:
                    fs.put(buffer_img.tobytes(), filename=filename, content_type="image/jpeg")
            except Exception as e:
                print("GridFS Image Error:", e)

            with app.app_context():
                db.session.add(Alert(alert_type="Unwanted Pose", user_email=user_email))
                db.session.add(ScreenshotAlert(image_path=filename, user_email=user_email, alert_type="Unwanted Pose"))
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print("DB Commit Error (Live):", e)

            video_filename = None
            current_time = time.time()
            if current_time - last_recording_time > 10:
                video_filename = f"{user_email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                Thread(target=save_incident_video, args=(list(frame_buffer), video_filename)).start()
                last_recording_time = current_time

            try:
                mapped_event = map_status(class_name)
                collection.insert_one({
                    "event": mapped_event,
                    "confidence": float(confidence),
                    "status": "Unsafe",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "video_file": video_filename
                })
                was_unsafe = True
            except Exception as e:
                print("MongoDB Insertion Error (Live):", e)

            if not sound_thread or not sound_thread.is_alive():
                sound_thread = Thread(target=play_alert_sound, args=(class_name,))
                sound_thread.start()

            unwanted_count = 0

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

def gen_frames_for_file(filepath, user_email):
    cap = cv2.VideoCapture(filepath)
    unwanted_count = 0
    threshold = 10
    sound_thread = None
    frame_buffer = deque(maxlen=150)
    last_recording_time = 0
    was_unsafe = False

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame_buffer.append(frame.copy())
        is_unwanted, class_name, confidence = detect_pose(frame)

        # Log "Safe" transition
        if not is_unwanted and was_unsafe:
            try:
                collection.insert_one({
                    "event": "Resumed Normal Driving (Video)",
                    "confidence": float(confidence),
                    "status": "Safe",
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "video_file": None
                })
                was_unsafe = False
            except Exception as e:
                print("Safe Log Error (Video):", e)

        label = f"{class_name}: {confidence*100:.1f}%"
        color = (0,0,255) if is_unwanted else (0,255,0)
        cv2.putText(frame, label, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

        if is_unwanted:
            unwanted_count += 1
        else:
            unwanted_count = 0
            sound_stop_event.set()

        if unwanted_count > threshold:
            filename = f"upload_{user_email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            
            try:
                ret_img, buffer_img = cv2.imencode('.jpg', frame)
                if ret_img:
                    fs.put(buffer_img.tobytes(), filename=filename, content_type="image/jpeg")
            except Exception as e:
                print("GridFS Image Error:", e)

            with app.app_context():
                db.session.add(Alert(alert_type="Unwanted Pose (Video)", user_email=user_email))
                db.session.add(ScreenshotAlert(image_path=filename, user_email=user_email, alert_type="Unwanted Pose (Video)"))
                
                # Use a separate context to commit because this is running in a generator thread
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print("DB Commit Error:", e)

            video_filename = None
            current_time = time.time()
            if current_time - last_recording_time > 10:
                video_filename = f"upload_{user_email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                Thread(target=save_incident_video, args=(list(frame_buffer), video_filename)).start()
                last_recording_time = current_time

            try:
                mapped_event = map_status(class_name)
                collection.insert_one({
                    "event": mapped_event,
                    "confidence": float(confidence),
                    "status": "Unsafe",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "video_file": video_filename
                })
                was_unsafe = True
            except Exception as e:
                print("MongoDB Insertion Error (Video):", e)

            if not sound_thread or not sound_thread.is_alive():
                sound_thread = Thread(target=play_alert_sound, args=(class_name,))
                sound_thread.start()

            unwanted_count = 0

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()


# ===================== ROUTES =====================

@app.route('/')
def index():
    return render_template('index.html')


# 🔥 FIXED SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None

    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not all([name, username, email, password]):
            error = "All fields required"

        elif len(password) < 8:
            error = "Password must be 8+ characters"

        else:
            user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()

            if user:
                return render_template('signup.html', error="User already exists!")

            try:
                new_user = User(name, username, email, password)
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for('login'))

            except:
                db.session.rollback()
                error = "Error creating account"

    return render_template('signup.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form['username']
        password = request.form['password']

        user = User.query.filter(
            (User.username == user_input) | (User.email == user_input)
        ).first()

        if user and user.check_password(password):
            session['user'] = user.email
            session['admin'] = user.email.endswith("@poseguard.com")
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="Invalid credentials")

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/video_feed')
def video_feed():
    if 'user' not in session:
        return redirect(url_for('login'))

    return Response(gen_frames(session['user']),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


    return Response(gen_frames_for_file(filepath, session['user']),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/process_video', methods=['POST'])
def process_video():
    if 'user' not in session:
        return redirect(url_for('login'))

    if 'video' not in request.files:
        return redirect(request.url)

    file = request.files['video']
    if file.filename == '' or not allowed_file(file.filename):
        return redirect(request.url)

    filename = secure_filename(file.filename)
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    file.save(temp_path)

    return render_template('video_upload.html', filename=filename)


@app.route('/video_upload')
def video_upload():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('video_upload.html')


@app.route('/process-video', methods=['POST'])
def process_video():
    if 'user' not in session:
        return redirect(url_for('login'))

    file = request.files['video']
    filename = secure_filename(file.filename)
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    file.save(temp_path)

    return render_template('video_upload.html', filename=filename)


# 🔥 FIXED REPORTS ROUTE
@app.route('/reports')
def reports():
    if 'user' not in session or not session.get('admin'):
        abort(403)

    alerts = Alert.query.order_by(Alert.timestamp.desc()).all()
    screenshots = ScreenshotAlert.query.order_by(ScreenshotAlert.timestamp.desc()).all()

    return render_template('reports.html', alerts=alerts, screenshots=screenshots)


@app.route('/admin')
def admin_portal():
    if 'user' not in session or not session.get('admin'):
        abort(403)

    shots = ScreenshotAlert.query.order_by(ScreenshotAlert.timestamp.desc()).all()
    return render_template('admin_portal.html', shots=shots)


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/records')
def view_records():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    try:
        # Fetch all records, sort by time descending using raw python if sort("_id", -1) fails
        records_data = list(collection.find().sort("_id", -1))
    except Exception as e:
        records_data = []
        print(f"Error fetching from MongoDB: {e}")
        
    return render_template('records.html', records=records_data)


@app.route('/information')
def information():
    return render_template('information.html')


@app.route('/media/<filename>')
def get_media(filename):
    try:
        import gridfs
        file_data = fs.get_last_version(filename)
        mime_type = "video/mp4" if filename.endswith(".mp4") else "image/jpeg"
        return Response(file_data.read(), mimetype=mime_type)
    except gridfs.errors.NoFile:
        abort(404)
    except Exception as e:
        print(f"GridFS Retrieval Error: {e}")
        abort(500)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


# ===================== RUN =====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
