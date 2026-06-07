from flask import Flask, render_template, request, redirect, url_for, session, Response, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt, cv2, os, tempfile, time, logging
import numpy as np
from datetime import datetime
from collections import deque
from threading import Thread, Event
from dotenv import load_dotenv
from pymongo import MongoClient
import gridfs
from werkzeug.utils import secure_filename
from pose_detection import detect_pose, preload_model, ensure_model_loaded, get_model_status

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)
logger = logging.getLogger('poseguard')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'changeme-poseguard-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///poseguard.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv'}

db = SQLAlchemy(app)

MONGO_URI = os.getenv('MONGO_URI', '')
mongo_client = None
mongo_db = None
fs = None

if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client['poseguard']
        fs = gridfs.GridFS(mongo_db)
        print("[PoseGuard] MongoDB connected")
    except Exception as e:
        print(f"[PoseGuard] MongoDB connection failed: {e}")


# ── Models ──────────────────────────────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def __init__(self, name, username, email, password):
        self.name = name
        self.username = username
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(100))
    user_email = db.Column(db.String(120))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ScreenshotAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(300))
    user_email = db.Column(db.String(120))
    alert_type = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class IncidentVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_path = db.Column(db.String(300))
    user_email = db.Column(db.String(120))
    alert_type = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ContactInquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    work_email = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

preload_model()


# ── Helpers ──────────────────────────────────────────────────────────────────

_camera = None


def get_camera():
    global _camera
    if _camera is None or not _camera.isOpened():
        _camera = cv2.VideoCapture(0)
        if not _camera.isOpened():
            print("[PoseGuard] Warning: Camera not found")
    return _camera


def map_status(class_name):
    return {
        "Normal Pose": "Safe",
        "Phone (Using)": "Phone",
        "Phone (Talking)": "Phone",
        "Looking Away": "Drowsy",
        "Distracted....": "Drowsy",
        "Drinking": "Unsafe",
        "Makeup": "Unsafe",
        "No Hands on Wheel": "Unsafe",
    }.get(class_name, "Unsafe")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _encode_status_frame(title, subtitle='', progress=0):
    """Render a placeholder JPEG frame while the model loads."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (15, 15, 30)
    cv2.rectangle(frame, (40, 40), (600, 440), (0, 243, 255), 2)
    cv2.putText(frame, title, (60, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 243, 255), 2)
    if subtitle:
        for i, line in enumerate(_wrap_text(subtitle, 52)):
            cv2.putText(frame, line, (60, 170 + i * 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    if progress > 0:
        bar_x, bar_y, bar_w, bar_h = 60, 360, 520, 22
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 60, 80), -1)
        fill_w = int(bar_w * min(progress, 100) / 100)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), (0, 200, 120), -1)
        cv2.putText(frame, f'{progress}%', (bar_x + bar_w // 2 - 30, bar_y + 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    ret, buffer = cv2.imencode('.jpg', frame)
    if ret:
        return (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    return None


def _wrap_text(text, width):
    words = text.split()
    lines, current = [], []
    for word in words:
        candidate = ' '.join(current + [word])
        if len(candidate) <= width:
            current.append(word)
        else:
            if current:
                lines.append(' '.join(current))
            current = [word]
    if current:
        lines.append(' '.join(current))
    return lines[:4]


def _wait_for_model_frames():
    """Yield loading/status frames until the model is ready or fails."""
    preload_model()
    while True:
        status = get_model_status()
        if status['state'] == 'ready':
            return
        if status['state'] == 'error':
            frame = _encode_status_frame(
                'Model Load Failed',
                status.get('error') or status['message'],
            )
            if frame:
                yield frame
            time.sleep(2)
            return
        frame = _encode_status_frame(
            'Loading AI Model…',
            status['message'],
            status.get('progress', 0),
        )
        if frame:
            yield frame
        time.sleep(0.4)


def play_alert_sound(class_name):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(f"Warning! {class_name} detected.")
        engine.runAndWait()
    except Exception as e:
        print(f"[PoseGuard] TTS error: {e}")


def save_incident_video(frames, video_filename, user_email, alert_type):
    if not fs:
        return
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mp4')
        os.close(tmp_fd)
        if not frames:
            return
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(tmp_path, fourcc, 10, (w, h))
        for f in frames:
            out.write(f)
        out.release()
        with open(tmp_path, 'rb') as f:
            file_id = fs.put(f, filename=video_filename, content_type='video/mp4')
        with app.app_context():
            record = IncidentVideo(video_path=str(file_id), user_email=user_email, alert_type=alert_type)
            db.session.add(record)
            db.session.commit()
    except Exception as e:
        print(f"[PoseGuard] save_incident_video error: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _process_frame_loop(cap, user_email):
    frame_buffer = deque(maxlen=150)
    unwanted_count = 0
    last_recording_time = 0
    last_status = "safe"
    sound_thread = None
    sound_stop_event = Event()

    while True:
        success, frame = cap.read()
        if not success:
            time.sleep(0.05)
            if not cap.isOpened():
                break
            continue

        frame_buffer.append(frame.copy())
        is_unwanted, class_name, confidence = detect_pose(frame)

        color = (0, 0, 255) if is_unwanted else (0, 255, 0)
        cv2.putText(frame, f"{class_name}: {confidence * 100:.1f}%", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

        if is_unwanted:
            unwanted_count += 1
        else:
            if last_status == "unsafe" and mongo_db is not None:
                try:
                    mongo_db.incidents.insert_one({
                        "event": "Resumed Normal Driving",
                        "user_email": user_email,
                        "status": "Safe",
                        "confidence": 0.0,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                except Exception:
                    pass
            unwanted_count = 0
            last_status = "safe"
            sound_stop_event.set()

        if unwanted_count > 10:
            last_status = "unsafe"
            timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            # Screenshot
            screenshot_id = None
            if fs:
                try:
                    _, buf = cv2.imencode('.jpg', frame)
                    screenshot_id = fs.put(buf.tobytes(), filename=f"shot_{timestamp_str}.jpg",
                                           content_type='image/jpeg')
                except Exception as e:
                    print(f"[PoseGuard] screenshot error: {e}")

            with app.app_context():
                try:
                    db.session.add(Alert(alert_type=class_name, user_email=user_email))
                    if screenshot_id:
                        db.session.add(ScreenshotAlert(
                            image_path=str(screenshot_id),
                            user_email=user_email,
                            alert_type=class_name,
                        ))
                    db.session.commit()
                except Exception as e:
                    print(f"[PoseGuard] DB error: {e}")
                    db.session.rollback()

            if time.time() - last_recording_time > 10:
                last_recording_time = time.time()
                video_filename = f"incident_{timestamp_str}.mp4"
                frames_copy = list(frame_buffer)
                t = Thread(target=save_incident_video,
                           args=(frames_copy, video_filename, user_email, class_name),
                           daemon=True)
                t.start()

            if mongo_db is not None:
                try:
                    mongo_db.incidents.insert_one({
                        "event": class_name,
                        "user_email": user_email,
                        "status": map_status(class_name),
                        "confidence": round(confidence * 100, 1),
                        "timestamp": datetime.utcnow().isoformat(),
                        "video_file": None,
                    })
                except Exception as e:
                    print(f"[PoseGuard] mongo insert error: {e}")

            if sound_thread is None or not sound_thread.is_alive():
                sound_stop_event.clear()
                sound_thread = Thread(target=play_alert_sound, args=(class_name,), daemon=True)
                sound_thread.start()

            unwanted_count = 0

        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


def gen_frames(user_email):
    yield from _wait_for_model_frames()
    cam = get_camera()
    if not cam.isOpened():
        frame = _encode_status_frame('Camera Unavailable', 'No webcam detected.')
        if frame:
            yield frame
        return
    yield from _process_frame_loop(cam, user_email)


def gen_frames_for_file(filepath, user_email):
    yield from _wait_for_model_frames()
    if get_model_status()['state'] != 'ready':
        return
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        frame = _encode_status_frame('Video Error', f'Could not open: {os.path.basename(filepath)}')
        if frame:
            yield frame
        return
    try:
        yield from _process_frame_loop(cap, user_email)
    finally:
        cap.release()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not all([name, username, email, password]):
            error = "All fields are required."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken."
        elif User.query.filter_by(email=email).first():
            error = "Email already registered."
        else:
            user = User(name=name, username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('signup.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()
        if user and user.check_password(password):
            session['user'] = user.email
            session['name'] = user.name
            session['admin'] = user.email.endswith('@poseguard.com')
            return redirect(url_for('dashboard'))
        error = "Invalid credentials. Please try again."
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


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


@app.route('/video_feed/<filename>')
def video_feed_with_filename(filename):
    if 'user' not in session:
        return redirect(url_for('login'))
    filepath = os.path.join(tempfile.gettempdir(), secure_filename(filename))
    return Response(gen_frames_for_file(filepath, session['user']),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_upload', methods=['GET', 'POST'])
def video_upload():
    if 'user' not in session:
        return redirect(url_for('login'))
    filename = None
    error = None
    if request.method == 'POST':
        file = request.files.get('video')
        if file and allowed_file(file.filename):
            if not ensure_model_loaded(timeout=120):
                status = get_model_status()
                error = status.get('error') or status['message']
            else:
                filename = secure_filename(file.filename)
                save_path = os.path.join(tempfile.gettempdir(), filename)
                file.save(save_path)
        else:
            error = 'Please upload a valid video file (MP4, AVI, MOV, or WMV).'
    model_status = get_model_status()
    return render_template(
        'video_upload.html',
        filename=filename,
        error=error,
        model_ready=model_status['state'] == 'ready',
    )


@app.route('/api/model/status')
def model_status_api():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    status = get_model_status()
    if status['state'] not in ('ready', 'loading'):
        preload_model()
    return jsonify(status)


@app.route('/reports')
def reports():
    if not session.get('admin'):
        return render_template('403.html'), 403
    alerts = Alert.query.order_by(Alert.timestamp.desc()).all()
    screenshots = ScreenshotAlert.query.order_by(ScreenshotAlert.timestamp.desc()).all()
    return render_template('reports.html', alerts=alerts, screenshots=screenshots)


@app.route('/admin')
def admin_portal():
    if not session.get('admin'):
        return render_template('403.html'), 403
    shots = ScreenshotAlert.query.order_by(ScreenshotAlert.timestamp.desc()).all()
    return render_template('admin_portal.html', shots=shots)


@app.route('/get-in-touch', methods=['POST'])
def get_in_touch():
    name = request.form.get('name', '').strip()
    work_email = request.form.get('work_email', '').strip()
    company = request.form.get('company', '').strip()
    message = request.form.get('message', '').strip()

    if not all([name, work_email, company, message]):
        return redirect(url_for('index', contact_error=1) + '#get-in-touch')

    try:
        inquiry = ContactInquiry(
            name=name,
            work_email=work_email,
            company=company,
            message=message,
        )
        db.session.add(inquiry)
        db.session.commit()
        if mongo_db is not None:
            mongo_db.contact_inquiries.insert_one({
                'name': name,
                'work_email': work_email,
                'company': company,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
            })
        logger.info('[PoseGuard] Contact inquiry from %s (%s)', name, work_email)
    except Exception as e:
        logger.error('[PoseGuard] Failed to save contact inquiry: %s', e)
        db.session.rollback()
        return redirect(url_for('index', contact_error=1) + '#get-in-touch')

    return redirect(url_for('index', contact_sent=1) + '#get-in-touch')


@app.route('/records')
def view_records():
    if 'user' not in session:
        return redirect(url_for('login'))
    records = []
    if mongo_db is not None:
        try:
            raw = mongo_db.incidents.find().sort('_id', -1)
            records = [dict(r, _id=str(r['_id'])) for r in raw]
        except Exception as e:
            print(f"[PoseGuard] records fetch error: {e}")
    return render_template('records.html', records=records)


@app.route('/information')
def information():
    return render_template('information.html')


@app.route('/media/<filename>')
def get_media(filename):
    if not fs:
        abort(404)
    try:
        import io
        from flask import send_file
        grid_out = fs.get_last_version(filename=filename)
        content_type = grid_out.content_type or 'application/octet-stream'
        return send_file(io.BytesIO(grid_out.read()), mimetype=content_type)
    except gridfs.errors.NoFile:
        abort(404)
    except Exception as e:
        print(f"[PoseGuard] media serve error: {e}")
        abort(500)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
