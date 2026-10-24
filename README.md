# 🌱 AI Farm Guardian

### Intelligent Crop Risk Analysis and Dynamic Intervention Prioritization System

AI Farm Guardian is an AI-powered agricultural support platform designed to help farmers monitor crop conditions, understand potential farming risks, and prioritize suitable interventions.

The platform combines crop analysis, weather intelligence, economic risk assessment, and AI-assisted recommendations to support better agricultural decision-making.

## 📌 Problem Statement

Farmers may face crop diseases, unpredictable weather, financial risks, and delays in taking appropriate action. When several problems occur simultaneously, deciding which issue needs immediate attention can be difficult.

AI Farm Guardian aims to address this challenge by identifying potential risks and prioritizing interventions according to their urgency and impact.

## 🎯 Objectives

* Identify potential crop health issues.
* Monitor weather conditions that may affect crops.
* Assess agricultural and economic risks.
* Prioritize interventions based on risk and urgency.
* Provide AI-assisted agricultural recommendations.
* Help farmers track treatments and important notifications.

## ✨ Key Features

### 1. Crop Image Scanner

Uses a locally trained four-class tomato classifier when its checkpoint is
installed, otherwise uses the configured Groq vision model
(`GROQ_VISION_MODEL`, default `qwen/qwen3.8-27b`). When you request diagnosis
and rescue guidance after a scan, the saved crop photo is sent to that Groq
vision model to review the local classifier prediction. Model confidence is an
estimate; measured accuracy is reported separately from the held-out test
split. Severity remains unassessed until entered as a field assessment.

### 2. Dynamic Intervention Prioritization

Ranks recorded farming assessments using severity, affected area, crop stage, and weather data when available. It is a transparent heuristic score, not an XGBoost model.

### 3. AI Rescue Planner

Provides general AI-assisted guidance when the backend provider is configured. It does not prescribe products or doses; farmers should confirm actions with local experts.

### 4. Weather Intelligence

Provides weather-related information to help farmers understand environmental conditions affecting their crops.

### 5. Economic Risk Analysis

Calculates affected crop value from farm-entered price and yield. Estimated losses require an explicit yield-reduction assumption.

### 6. Farm Management

Allows users to manage farm-related information through the application.

### 7. Treatment Tracking

Supports tracking of farming treatments and related activities.

### 8. AI Farm Assistant

Provides an AI-assisted interface for agricultural questions and farming guidance.

### 9. Dashboard and Notifications

Provides a central dashboard for important farming information and notifications.

## 🛠️ Technologies Used

### Frontend

* React.js
* Vite
* JavaScript
* Tailwind CSS
* HTML
* CSS

### Backend

* Python
* FastAPI
* REST APIs

### Database

* MySQL

### Artificial Intelligence and External Services

* Groq API for AI-assisted features
* OpenWeatherMap API for weather information
* Image analysis through the crop-vision service

*The exact models and algorithms depend on the current implementation of the corresponding services.*

## 🏗️ Project Architecture

The application follows a frontend-backend architecture.

1. The user interacts with the React frontend.
2. The frontend sends requests to the Python backend through REST APIs.
3. The backend processes requests and interacts with the database or relevant services.
4. AI and weather services provide information when configured.
5. The backend returns results to the frontend for display.

## 📂 Project Structure

```text
ai-farm-guardian/
│
├── backend/
│   ├── main.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── requirements.txt
│   │
│   ├── routers/
│   │   ├── auth_router.py
│   │   ├── chat_router.py
│   │   ├── dashboard_router.py
│   │   ├── economic_router.py
│   │   ├── farms_router.py
│   │   ├── fields_router.py
│   │   ├── notifications_router.py
│   │   ├── priority_router.py
│   │   ├── rescue_router.py
│   │   ├── scans_router.py
│   │   ├── treatments_router.py
│   │   └── weather_router.py
│   │
│   └── services/
│       ├── ai_assistant_service.py
│       ├── ai_planner_service.py
│       ├── ai_service.py
│       ├── economic_engine.py
│       ├── priority_engine.py
│       ├── vision_service.py
│       └── weather_service.py
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── context/
│   │   └── pages/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── package.json
├── package-lock.json
└── README.md
```

## ⚙️ Installation and Setup

### Prerequisites

Install Python 3.12 or 3.13, Node.js 22.12 or newer, npm, and MySQL 8. Use
your existing local MySQL database and tables.

### Configure once

Run these commands in PowerShell from the project root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm run install:all
```

The backend reads its local MySQL connection from `backend\.env`. The defaults
are `127.0.0.1:3306`, database `farm_guardian`, user `root`; the settings you
already have in that file are used directly. No separate setup command is
needed. Run:

```powershell
npm run dev
```

The app connects to your existing database and does not create, migrate, or
delete it.

Groq and OpenWeather keys are optional. Configure `GROQ_API_KEY` in
`backend\.env` to enable image-based diagnosis/rescue guidance, Groq-backed
crop scanning when no trained checkpoint is installed, and other Groq
features. Set `GROQ_VISION_MODEL` only if you want to override the default
vision model. Weather requires its key and farm coordinates. Never commit
private `.env` files.

### Run locally

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs`.
`/health` checks the process and `/ready` checks the database and reports the
crop-model status. MySQL must be reachable before the backend starts.

If you already have data in `backend\farmguardian.db`, migrate it only after
configuring an empty MySQL database in `backend\.env`:

```powershell
backend\.venv\Scripts\python.exe backend\migrate_sqlite_to_mysql.py
```

The migration copies rows and does not delete or modify the SQLite source. It
refuses to write to a non-empty MySQL target. Review the data first because
older local databases may include demonstration records.

For an already-created MySQL database from an earlier version, apply
`backend\migrations\001_treatment_fields.sql` once before starting the API.

### Crop classifier training

The training script uses four tomato classes from the provided PlantVillage
dataset: healthy, early blight, late blight, and bacterial spot. It samples
at most 1,000 unique images per class, creates deterministic stratified
train/validation/test splits, and reports accuracy and per-class metrics on
the held-out test split. The completed run reached **81.33% accuracy on 600
held-out images** (150 per class). Recall was 88.67% for healthy, 66.00% for
early blight, 77.33% for late blight, and 93.33% for bacterial spot. These
results describe this PlantVillage split only; they do not guarantee accuracy
on field photographs or represent Groq results.

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-ml.txt
backend\.venv\Scripts\python.exe -m backend.ml.train --epochs 5
```

Training writes `backend\models\efficientnetv2_s.pth` and
`backend\models\efficientnetv2_s.test-metrics.json`. The checkpoint filename
is retained for compatibility; its embedded metadata identifies the actual
MobileNetV3-Small architecture and four supported classes. The backend loads
that metadata when using the local model. If the checkpoint is absent, Groq
vision remains the scanner fallback when configured.

### Deployment

- **MySQL:** create the database and restricted user, then set `DATABASE_URL`.
- **Render:** deploy FastAPI with `python -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT`; configure `DATABASE_URL`, `JWT_SECRET`, `ALLOWED_ORIGINS`, and optional service keys. Provide the model checkpoint as a deployment artifact or persistent disk; Render's ephemeral disk is not durable.
- **Vercel:** deploy `frontend`, set `VITE_API_BASE_URL` to the public FastAPI origin ending in `/api`, and set `ALLOWED_ORIGINS` on the backend to the exact Vercel origin. Set `COOKIE_SECURE=true` for HTTPS deployment.
- Keep secrets out of frontend environment variables and source control.

### API groups

FastAPI Swagger documentation at `/docs` lists the available endpoints:
authentication (`/api/auth`), farms and fields (`/api/farms`, `/api/fields`),
scans (`/api/scans`), priority (`/api/priority`), weather (`/api/weather`),
rescue (`/api/rescue`), economic estimates (`/api/economic`), treatments
(`/api/treatments`), notifications (`/api/notifications`), chat (`/api/chat`),
and dashboard summary (`/api/dashboard`).

## 🔐 Security

* Keep API keys in private environment files.
* Do not commit `.env` files.
* Do not upload virtual environments or `node_modules`.
* Use secure, unique secrets for authentication.
* Review environment variables before publishing the project.

## 🚀 Future Enhancements

* Improve crop disease identification using validated machine learning models.
* Refine intervention prioritization using crop severity, urgency, weather conditions, and economic impact.
* Add more crop varieties and regional agricultural recommendations.
* Improve multilingual support for farmers.
* Provide more detailed risk reports and treatment histories.
* Validate AI recommendations with agricultural experts and reliable datasets.

## 🎓 Project Domain

Artificial Intelligence | Machine Learning | Smart Agriculture | Decision Support Systems

## 👩‍💻 Developer

**Madhu**

AI and Data Science Engineering Student

## 📄 License

A license has not yet been specified. Add an appropriate open-source license if you decide to distribute the project under one.
