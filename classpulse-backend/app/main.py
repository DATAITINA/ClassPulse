import json
from collections import Counter

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import ai, crud, schemas
from .db import Base, engine, get_db

load_dotenv()

Base.metadata.create_all(bind=engine)


def ensure_feedback_analysis_columns() -> None:
    inspector = inspect(engine)
    if "feedback" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("feedback")}
    missing = []
    if "sentiment" not in existing_columns:
        missing.append("ALTER TABLE feedback ADD COLUMN sentiment VARCHAR(20)")
    if "key_issues" not in existing_columns:
        missing.append("ALTER TABLE feedback ADD COLUMN key_issues TEXT")
    if "suggestions" not in existing_columns:
        missing.append("ALTER TABLE feedback ADD COLUMN suggestions TEXT")

    if not missing:
        return

    with engine.begin() as conn:
        for statement in missing:
            conn.execute(text(statement))


ensure_feedback_analysis_columns()

app = FastAPI(title="ClassPulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def parse_json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


@app.post("/feedback", response_model=schemas.AnalysisResponse)
def submit_feedback(payload: schemas.FeedbackCreate, db: Session = Depends(get_db)):
    analysis = ai.analyze_feedback(payload.feedback_text)
    crud.create_feedback(db, payload, analysis)
    return analysis


@app.get("/insights", response_model=schemas.InsightsResponse)
def get_insights(db: Session = Depends(get_db)):
    feedback_list = crud.get_all_feedback(db)
    total_feedback = len(feedback_list)

    sentiment_counts = Counter()
    issue_counts = Counter()
    issue_labels = {}

    for feedback in feedback_list:
        sentiment = (feedback.sentiment or "neutral").lower().strip()
        if sentiment not in {"positive", "negative", "neutral"}:
            sentiment = "neutral"
        sentiment_counts[sentiment] += 1

        for issue in parse_json_list(feedback.key_issues):
            normalized = issue.lower()
            issue_counts[normalized] += 1
            issue_labels.setdefault(normalized, issue)

    top_issues = [issue_labels[key] for key, _ in issue_counts.most_common(5)]

    return schemas.InsightsResponse(
        total_feedback=total_feedback,
        sentiment_breakdown={
            "positive": sentiment_counts.get("positive", 0),
            "negative": sentiment_counts.get("negative", 0),
            "neutral": sentiment_counts.get("neutral", 0),
        },
        top_issues=top_issues,
    )
