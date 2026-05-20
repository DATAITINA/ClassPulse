from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    course_name: str = Field(..., min_length=1)
    lecturer_name: str = Field(..., min_length=1)
    feedback_text: str = Field(..., min_length=1)


class AnalysisResponse(BaseModel):
    sentiment: str
    key_issues: List[str]
    suggestions: List[str]


class InsightsResponse(BaseModel):
    total_feedback: int
    sentiment_breakdown: Dict[str, int]
    top_issues: List[str]


class FeedbackItem(BaseModel):
    id: int
    course_name: str
    lecturer_name: str
    feedback_text: str
    sentiment: str | None = None
    created_at: datetime
