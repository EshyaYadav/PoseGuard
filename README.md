# HOW TO RUN — PoseGuard

A step-by-step guide for setting up and running PoseGuard in VS Code.

---

## Section 1 — System Requirements

- **Python 3.9, 3.10, or 3.11** (NOT 3.12 — TensorFlow doesn't support it yet)
- **VS Code** with the Python extension installed
- A working **webcam** (for live monitoring)
- A free **MongoDB Atlas** account (mongodb.com)
- Git (optional)

---

## Section 2 — What to Install on Your OS

### Windows
No extra system packages needed.
Just install Python from [python.org](https://python.org) and check **"Add to PATH"** during installation.

### Linux (Ubuntu / Debian)
```bash
sudo apt update
sudo apt install -y python3-dev python3-pip python3-venv \
    libespeak1 espeak ffmpeg libsm6 libxext6 libxrender-dev portaudio19-dev
```

### macOS
```bash
brew install espeak portaudio ffmpeg
```

---

## Section 3 — Step-by-Step Setup

### Step 1
Extract the ZIP file and open the `poseguard` folder in VS Code.

### Step 2
Open the VS Code terminal: **Ctrl+`** (backtick) or **View → Terminal**

### Step 3 — Create a virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4 — Install Python packages
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5 — Add your model file
Copy your trained model file into the `model/` folder:
```
poseguard/model/poseguard_model.h5
```
The path **must** be exactly: `poseguard/model/poseguard_model.h5`

### Step 6 — Set up the .env file

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows:**
```bash
copy .env.example .env
```

Then open `.env` in VS Code and fill in the three values:

- `MONGO_URI` — your MongoDB Atlas connection string
- `SECRET_KEY` — any long random string (e.g. `myS3cr3tKey123!`)
- `DATABASE_URL` — leave as default (`sqlite:///poseguard.db`)

**How to get your MongoDB URI:**
1. Go to [mongodb.com](https://mongodb.com) and sign up for free
2. Create a free cluster
3. Click **Connect** → **Drivers** → copy the connection string
4. Replace `<password>` with your real Atlas password
5. Paste it as `MONGO_URI` in your `.env` file
6. In MongoDB Atlas → **Network Access** → **Add IP Address** → **Allow Access from Anywhere** (0.0.0.0/0)

### Step 7 — Run the project
```bash
python app.py
```
Open your browser at: **http://localhost:5000**

---

## Section 4 — How to Use PoseGuard

1. Go to `http://localhost:5000` → click **Login** → click **Create an account**
2. Sign up with any email. Use an `@poseguard.com` email to get **admin access**.
3. After login → the **Dashboard** shows your live webcam feed with real-time pose detection.
4. Go to **📹 Video Analysis** to upload a recorded video file for analysis.
5. Go to **📁 Incident Records** to view all logged detections from MongoDB.
6. Admin accounts also see: **Reports** page and **Admin Portal**.

---

## Section 5 — Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'cv2'` | Run `pip install opencv-python` |
| `No module named 'pyttsx3'` | Run `pip install pyttsx3` |
| Black screen on Dashboard | Check your webcam is connected and not in use by another app |
| `Error loading model` | Make sure `poseguard_model.h5` is inside the `model/` folder |
| MongoDB connection error | Check your `MONGO_URI` in `.env` and whitelist your IP in Atlas |
| No voice alerts on Linux | Run `sudo apt install espeak` |
| `python` not found on macOS/Linux | Use `python3` instead of `python` |
| Port 5000 already in use | Change `port=5000` to `port=5001` in the last line of `app.py` |

---

## Section 6 — VS Code Tips

- Install the **Python** extension by Microsoft in VS Code
- Select your venv interpreter: **Ctrl+Shift+P** → "Python: Select Interpreter" → choose `venv`
- To stop the server: press **Ctrl+C** in the terminal
