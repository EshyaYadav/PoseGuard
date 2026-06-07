<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:FF4B2B,100:FF416C&height=200&section=header&text=PoseGuard&fontSize=70&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=AI-Powered%20Driver%20Safety%20Monitoring%20System&descAlignY=60&descSize=18" width="100%"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-Keras-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)](https://tensorflow.org)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)

<br/>

> **Real-time AI system that monitors drivers for unsafe behaviors — drowsiness, phone usage, and distraction — with instant voice alerts and fleet owner dashboards.**

</div>

---

## What is PoseGuard?

PoseGuard uses a trained Keras model (`poseguard_model.h5`) with OpenCV to classify driver behavior from a live webcam or uploaded video. Each frame is resized to 224×224, normalized, and passed through the model. If the predicted class is unsafe **and** confidence exceeds 70%, it triggers a voice alert, saves a screenshot and incident video clip to MongoDB GridFS, and logs the event for fleet owners.

---

## Detected Behaviors

| Class | Label | Status |
|---|---|---|
| 0 | Normal Pose | ✅ Safe |
| 1 | Phone (Using) | 🚨 Unsafe |
| 2 | Phone (Talking) | 🚨 Unsafe |
| 3 | Distracted.... | ⚠️ Drowsy |
| 4 | Drinking | 🚨 Unsafe |
| 5 | No Hands on Wheel | 🚨 Unsafe |
| 6 | Makeup | 🚨 Unsafe |
| 7 | Looking Away | ⚠️ Drowsy |

---

## How It Works

```
Webcam / Video File
      │
      ▼
OpenCV frame capture
      │
      ▼
Resize to 224×224 → Normalize [0,1]
      │
      ▼
poseguard_model.h5  (Keras CNN)
      │
      ▼
Predicted class + confidence score
      │
      ├── confidence < 0.7  →  Skip (too uncertain)
      │
      └── confidence ≥ 0.7 + unsafe class
            │
            ├── 10 consecutive frames threshold (avoids false positives)
            │
            ▼
        Voice Alert (pyttsx3, separate thread)
        Screenshot → MongoDB GridFS
        Incident Video (150-frame buffer) → MongoDB GridFS
        Alert + metadata → SQLite + MongoDB
        10s cooldown before next video save
```

---

## Features

- 🎯 Live webcam monitoring and pre-recorded video upload mode
- 🧠 Keras CNN model with 70% confidence threshold to filter false positives
- 🔊 Real-time voice warnings via pyttsx3 (non-blocking thread)
- 📸 Auto screenshot on detection, stored in MongoDB GridFS
- 🎬 150-frame rolling buffer — saves incident clip around the event
- 📊 Fleet owner admin dashboard with screenshot gallery and alert history
- 📋 MongoDB incident logs with event type, confidence, timestamp, video reference
- 🔐 User auth with bcrypt hashing; admin role via `@poseguard.com` email
- ☁️ Vercel + Gunicorn deployment ready

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Keras CNN (`poseguard_model.h5`), 224×224 input, 8-class output |
| Computer Vision | OpenCV 4.x — frame capture, resize, MJPEG streaming |
| Backend | Flask, Flask-SQLAlchemy |
| Primary DB | MongoDB Atlas + GridFS (incident logs, screenshots, video clips) |
| Secondary DB | SQLite (users, alert records, screenshot metadata) |
| Auth | bcrypt, Flask sessions |
| Voice Alerts | pyttsx3 |
| Deployment | Vercel (serverless), Gunicorn |

---

## Project Structure

```
poseguard/
├── app.py                  # Flask routes, video streaming, auth, alert logic
├── pose_detection.py       # Model loading, frame preprocessing, inference
├── requirements.txt
├── vercel.json
├── model/
│   └── poseguard_model.h5  # Trained Keras model
├── static/                 # CSS, JS, processed output
└── templates/              # Jinja2 templates
    ├── index.html
    ├── dashboard.html
    ├── login.html
    ├── signup.html
    ├── admin_portal.html
    ├── reports.html
    ├── records.html
    └── video_upload.html
```

---

## Setup & Run

**Prerequisites:** Python 3.9+, webcam, MongoDB Atlas account

```bash
# Clone
git clone https://github.com/UjjwalKumarKannojiya/poseguard.git
cd poseguard

# Virtual environment
python -m venv venv
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows

# Install
pip install -r requirements.txt

# Environment — create a .env file
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/
SECRET_KEY=your_secret_key_here
DATABASE_URL=sqlite:///poseguard.db

# Run
python app.py
# Open http://localhost:5000
```

---

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:FF416C,100:FF4B2B&height=120&section=footer" width="100%"/>
</div>
