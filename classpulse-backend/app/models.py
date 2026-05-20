from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime

from .db import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    course_name = Column(String(255), nullable=False)
    lecturer_name = Column(String(255), nullable=False)
    feedback_text = Column(Text, nullable=False)
    sentiment = Column(String(20), nullable=True)
    key_issues = Column(Text, nullable=True)
    suggestions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
