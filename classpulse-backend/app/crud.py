import json
from typing import Any

from sqlalchemy.orm import Session

from . import models, schemas


def create_feedback(
    db: Session, feedback: schemas.FeedbackCreate, analysis: dict[str, Any]
) -> models.Feedback:
    db_feedback = models.Feedback(
        course_name=feedback.course_name,
        lecturer_name=feedback.lecturer_name,
        feedback_text=feedback.feedback_text,
        sentiment=analysis["sentiment"],
        key_issues=json.dumps(analysis["key_issues"]),
        suggestions=json.dumps(analysis["suggestions"]),
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


def get_all_feedback(db: Session) -> list[models.Feedback]:
    return db.query(models.Feedback).order_by(models.Feedback.created_at.desc()).all()
