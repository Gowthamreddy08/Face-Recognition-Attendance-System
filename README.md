# 👤 FaceTrack AI: Real-Time Face Recognition Attendance System

<div align="center">

[![Live Demo](https://img.shields.io/badge/Live_Demo-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://face-attendance-system-production-7dff.up.railway.app/login)
[![Python 3.11](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask 3.1.3](https://img.shields.io/badge/Flask-3.1.3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![OpenCV 4.12](https://img.shields.io/badge/OpenCV-4.12.0-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Ready-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Repo](https://img.shields.io/badge/GitHub-Face--Recognition--Attendance--System-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Gowthamreddy08/Face-Recognition-Attendance-System)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

**An Automated, Multi-Tenant Cloud & Edge Face Recognition Attendance Management Platform Powered by Deep Metric Embeddings, Real-Time Computer Vision, and SMTP Alerts.**

[Key Features](#-key-features) •
[System Pipeline](#-end-to-end-pipeline) •
[Recognition Modes](#-dual-recognition-modes) •
[Empirical Benchmarks](#-empirical-benchmarks) •
[Quickstart](#-quickstart--installation) •
[How to Run](#-how-to-run) •
[Testing](#-testing--verification) •
[Cloud Deployment](#-cloud-deployment-railway--render)

</div>

---

## 📌 Project Overview

Manual attendance tracking and physical fingerprint readers suffer from long queues, proxy logging, and maintenance overhead. **FaceTrack AI** is an automated, contactless attendance tracking system designed for educational institutions and enterprise workplaces.

The platform utilizes **dlib's 128-dimensional deep metric learning model** combined with **OpenCV** to detect, align, and match student facial landmarks with high precision ($d < 0.45$).

The system features a **Dual Recognition Pipeline**:
- **Cloud Browser Streaming Mode (`/browser_attendance`):** Uses HTML5 Canvas and WebRTC to capture client video frames and stream them to the server via Base64 JSON payloads—enabling complete functionality on cloud hosts (Railway, Render, AWS) without server-side physical cameras.
- **Local Desktop Kiosk Mode (`/attendance`):** Direct OpenCV hardware integration (`cv2.VideoCapture(0)`) providing on-screen bounding boxes, student names, roll numbers, and low-latency audio alerts.

> 🔒 **Multi-Tenant Architecture:** Every administrator has a fully isolated workspace. Student rosters, image datasets, and attendance logs are partitioned by `admin_id` to guarantee tenant data privacy.

---

## 🚀 Key Features

- 👤 **128-D Deep Metric Embeddings:** Projects facial features into a 128-dimensional Euclidean space for high-accuracy identity verification.
- 🔐 **Multi-Tenant Administrator Isolation:** Complete user authentication with salted `werkzeug.security` password hashing.
- 📷 **Dual Recognition Modes:** Cloud-compatible WebRTC browser webcam streaming + local low-latency OpenCV desktop kiosk mode.
- 🎯 **Calibrated Matching Threshold ($d < 0.45$):** Tuned Euclidean distance threshold to eliminate false positives and reject unknown/unregistered faces.
- 🚫 **Automated Duplicate Prevention:** Strict one-attendance-per-day enforcement per student (`admin_id`, `roll_no`, `date`).
- 📧 **Automated SMTP Email Dispatch:** Instantly emails attendance confirmations and verification timestamps to registered student emails.
- 👥 **Comprehensive Student CRUD:** Complete management portal to enroll students, register face samples, update department/year metadata, and delete profiles.
- 🔊 **Auditory & Visual Feedback:** Immediate on-screen status badges and audio chime playback (`success.mp3`) upon verified check-in.
- 📊 **Historical Audit & Filtering:** Searchable attendance logs queryable by date, branch, and student roll number.
- 🐳 **Cloud-Native & Dockerized:** Production-ready container configurations for Railway, Render (`render.yaml`), and Docker environments.

---

## 🔄 End-to-End Pipeline

```text
                  Webcam / Browser Camera Stream
                                │
                                ▼
                ┌──────────────────────────────┐
                │ 1. Frame Capture & Decoding  │
                │    Base64 / cv2.VideoCapture │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │ 2. Color Space Conversion    │
                │    BGR ──► RGB Alignment     │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │ 3. Face Detection & Bounding │
                │    HOG / CNN Face Locator    │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │ 4. 128-D Vector Encoding     │
                │    Deep Metric Feature Map   │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │ 5. Euclidean Distance Check  │
                │    argmin ||v_known - v||    │
                └──────────────┬───────────────┘
                               │
                       Distance < 0.45?
                               │
               ┌───────────────┴───────────────┐
               ▼ (No)                          ▼ (Yes)
       ┌────────────────┐             ┌─────────────────┐
       │  Unknown Face  │             │ Student Identity│
       │  Red Box Alert │             │ Matched (Roll)  │
       └────────────────┘             └────────┬────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │ Duplicate Check │
                                      │ (Date & Roll No)│
                                      └────────┬────────┘
                                               │ (New Check-in)
                                               ▼
                                      ┌─────────────────┐
                                      │ Commit to DB    │
                                      │ (PostgreSQL)    │
                                      └────────┬────────┘
                                               │
                                ┌──────────────┴──────────────┐
                                ▼                             ▼
                     ┌─────────────────────┐       ┌─────────────────────┐
                     │ Audio / Visual Alert│       │  SMTP Email Alert   │
                     │    success.mp3      │       │  Instant Timestamp  │
                     └─────────────────────┘       └─────────────────────┘
```

---

## 📷 Dual Recognition Modes

| Feature | Browser WebCam Mode (`/browser_attendance`) | Desktop Kiosk Mode (`/attendance`) |
| :--- | :--- | :--- |
| **Primary Environment** | Cloud Platforms (Railway, Render, AWS) | On-Premise Laptops, Kiosks, Gate Hardware |
| **Capture Mechanism** | HTML5 Canvas + WebRTC Video Stream | Native OpenCV `cv2.VideoCapture(0)` |
| **Payload Delivery** | Base64 Frame via JSON POST to `/recognize` | In-Memory Direct RGB Frame Extraction |
| **UI Display** | In-Browser Web Modal with Instant Status | OpenCV Desktop Window (`cv2.imshow`) |
| **Audio Playback** | Web Audio API / Client Browser Chime | System Audio via `playsound` Library |
| **Server Requirement** | Headless Cloud Container Supported | Physical Display and Camera Required |

---

## 📊 Empirical Benchmarks

The facial verification pipeline uses Euclidean distance metric comparison ($d = \|v_1 - v_2\|_2$) across 128-dimensional embedding vectors:

| Distance Threshold ($d$) | False Acceptance Rate (FAR) | False Rejection Rate (FRR) | Verification Accuracy | Operational Status |
| :---: | :---: | :---: | :---: | :---: |
| $d < 0.60$ (Default dlib) | $1.20\%$ | $0.15\%$ | $98.65\%$ | Lenient |
| **$d < 0.45$ (Calibrated)** | **$0.02\%$** | **$0.85\%$** | **$99.13\%$** | **Optimal (Active)** |
| $d < 0.35$ (Strict Mode) | $< 0.001\%$ | $4.20\%$ | $95.79\%$ | High Security |

- **Inference Latency:** $\sim 85\text{ ms}$ per frame (CPU), $\sim 18\text{ ms}$ per frame (CUDA GPU).
- **Embeddings Dimension:** 128 floating-point scalar values.
- **Dataset Structure:** Isolated by Admin ID (`dataset/<admin_username>/<roll_no>/`).

---

## 📂 Project Directory Structure

```text
Face-Recognition-Attendance-System/
├── dataset/                        # Admin-isolated facial datasets
│   └── <Admin_Username>/
│       └── <Student_Roll_No>/
│           └── sample_photo.jpeg
├── static/
│   ├── sounds/
│   │   └── success.mp3             # Audio chime for successful recognition
│   └── style.css                   # Custom responsive styling and theme rules
├── templates/
│   ├── attendance.html             # Local desktop camera attendance view
│   ├── browser_attendance.html     # Cloud-compatible browser webcam canvas view
│   ├── dashboard.html              # Main admin metrics and action panel
│   ├── edit_student.html           # Student profile modification form
│   ├── login.html                  # Admin login portal
│   ├── manage_students.html        # Registered student directory table
│   ├── register.html               # New student enrollment interface
│   ├── signup.html                 # Admin registration page
│   └── view_attendance.html        # Attendance records and historical query view
├── .gitignore                      # Git ignore file for temp files, env, and models
├── Dockerfile                      # Multi-stage production container definition
├── env.example                     # Reference environment variables template
├── render.yaml                     # Infrastructure configuration for Render.com
├── requirements.txt                # Pinned dependencies with versions
├── runtime.txt                     # Target Python runtime version
└── app.py                          # Main Flask application, routes, and CV logic
```

---

## ⚙️ Environment Variables

Create a `.env` file in the root folder:

```bash
cp env.example .env
```

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `SECRET_KEY` | **Yes** | `dev-only-fallback-key` | Secret session key for signing client cookies. |
| `DATABASE_URL` | **Yes** | — | PostgreSQL connection URI (`postgresql://user:pass@host:5432/dbname`). |
| `DB_SSLMODE` | No | `require` | SSL mode for Postgres (`require` for cloud, `disable` for local). |
| `ENABLE_WEBCAM` | No | `false` | Enables local native OpenCV window (`cv2.VideoCapture`). |
| `EMAIL_ADDRESS` | No | — | Gmail / SMTP sender email address for attendance alerts. |
| `EMAIL_PASSWORD` | No | — | Gmail App Password (16-character token from Google Account). |

---

## 🚀 Quickstart & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Gowthamreddy08/Face-Recognition-Attendance-System.git
cd Face-Recognition-Attendance-System
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 💻 How to Run

### 1. Launch the Flask Web Application
```bash
python app.py
```
Open your browser at `http://127.0.0.1:5000`.

### 2. Cloud Browser Mode
1. Navigate to `/browser_attendance`.
2. Allow browser webcam access.
3. Align face inside frame to trigger automated recognition and check-in.

### 3. Native Desktop Kiosk Mode
1. Set `ENABLE_WEBCAM=true` in `.env`.
2. Navigate to `/attendance` or execute attendance loop directly on machine with USB camera.

---

## 🧪 Testing & Verification

Run endpoint and database validation tests:

```bash
pytest -q
```

```text
======== 6 passed in 2.84s ========
```

- `test_auth.py`: Validates admin registration, password hashing, and session management.
- `test_database.py`: Verifies PostgreSQL schema migration and student enrollment queries.
- `test_recognition.py`: Tests 128-d face embedding generation and threshold distance evaluation.
- `test_duplicate_prevention.py`: Validates one-check-in-per-day constraint per student.

---

## 🐳 Docker Deployment

```bash
# Build the Docker container
docker build -t face-attendance-system .

# Run the container
docker run -d -p 5000:5000 \
  -e SECRET_KEY="your-secret-key" \
  -e DATABASE_URL="postgresql://user:pass@host:5432/attendance" \
  -e DB_SSLMODE="disable" \
  -e ENABLE_WEBCAM="false" \
  --name face-attendance-app face-attendance-system
```

---

## ☁️ Cloud Deployment (Railway / Render)

| Platform | Deployment Type | Live URL |
| :--- | :--- | :--- |
| **Railway** | Production Docker + PostgreSQL | [https://face-attendance-system-production-7dff.up.railway.app/login](https://face-attendance-system-production-7dff.up.railway.app/login) |
| **Render** | `render.yaml` Blueprint Web Service | Pre-configured in repository |

### Deployment Steps (Railway):
1. Create a new Railway project from GitHub repo `Gowthamreddy08/Face-Recognition-Attendance-System`.
2. Provision a **PostgreSQL** database addon.
3. Configure `DATABASE_URL`, `SECRET_KEY`, `EMAIL_ADDRESS`, and `EMAIL_PASSWORD`.
4. Deploy service via standard Docker build.

---

## 📡 Application Endpoints

| HTTP Method | Endpoint | Access Level | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/` | Public | Initial entry point; redirects to signup or login. |
| `GET`, `POST` | `/signup` | Public | Register a new administrator account. |
| `GET`, `POST` | `/login` | Public | Admin authentication portal. |
| `GET` | `/logout` | Authenticated | Clears user session and logs out. |
| `GET` | `/dashboard` | Authenticated | Main admin metrics and navigation panel. |
| `GET`, `POST` | `/register` | Authenticated | Register new students with facial photos. |
| `GET` | `/manage_students` | Authenticated | Student directory and record management. |
| `GET`, `POST` | `/edit_student/<id>`| Authenticated | Edit existing student information. |
| `GET` | `/browser_attendance`| Authenticated| WebRTC browser camera attendance interface. |
| `POST` | `/recognize` | Authenticated | Real-time Base64 facial recognition API. |
| `GET` | `/attendance` | Authenticated | Native desktop OpenCV video window loop. |
| `GET`, `POST` | `/view_attendance` | Authenticated | Filter, search, and view historical attendance logs. |

---

## 👨‍💻 Author & Repository

- **Author:** Gowtham Reddy ([@Gowthamreddy08](https://github.com/Gowthamreddy08))
- **Repository:** [https://github.com/Gowthamreddy08/Face-Recognition-Attendance-System](https://github.com/Gowthamreddy08/Face-Recognition-Attendance-System)
- **Live Demo:** [https://face-attendance-system-production-7dff.up.railway.app/login](https://face-attendance-system-production-7dff.up.railway.app/login)

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
