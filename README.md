# ClassPulse

**AI-Powered Real-time Classroom Feedback & Engagement Platform**

## Problem
Teachers in Nigerian schools struggle to get honest, real-time feedback from students and often lack data-driven insights to improve teaching.

## Solution
ClassPulse allows students to give anonymous feedback, rate classes, and ask questions. Teachers get AI-generated insights, summaries, and suggestions.

## Key Features
- Real-time student feedback
- AI analysis of classroom sentiment and performance (OpenAI integration)
- Anonymous polling and Q&A
- Teacher dashboard with insights

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy + OpenAI
- **Frontend**: React + Vite
- **Database**: SQLite

## Live Demo / Screenshots
(Add screenshots here later)

## How to Run Locally
```bash
# Backend
cd classpulse-backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd classpulse-frontend
npm install
npm run dev
