from datetime import datetime
from typing import Dict, List, Literal

from pydantic import BaseModel, Field


RoleType = Literal["student", "lecturer", "admin"]
ModerationStatus = Literal["allowed", "warn", "blocked"]


class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    role: RoleType
    institution: str | None = Field(default=None, max_length=120)


class UserLogin(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: RoleType
    institution: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class CourseCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=40)
    description: str | None = Field(default=None, max_length=400)


class CourseJoin(BaseModel):
    join_code: str = Field(..., min_length=4, max_length=20)


class CourseResponse(BaseModel):
    id: int
    title: str
    code: str
    description: str | None = None
    join_code: str | None = None
    lecturer_name: str
    member_count: int
    created_at: datetime


class FeedbackCreate(BaseModel):
    course_id: int
    feedback_text: str = Field(..., min_length=1)
    mood_before: str | None = Field(default=None, max_length=50)
    mood_after: str | None = Field(default=None, max_length=50)


class PulseCheckResponse(BaseModel):
    mood_before: str | None = None
    mood_after: str | None = None
    mood_shift: str | None = None


class AnalysisResponse(BaseModel):
    accepted: bool
    moderation_status: ModerationStatus
    moderation_message: str
    respectful_rewrite: str | None = None
    anonymous_alias: str | None = None
    sentiment: str
    key_issues: List[str]
    suggestions: List[str]
    strengths: List[str]
    next_step_ai: str
    pulse_check: PulseCheckResponse


class FairViewResponse(BaseModel):
    enough_data: bool
    minimum_responses: int
    fairness_note: str


class PulseOverviewResponse(BaseModel):
    mood_before_breakdown: Dict[str, int]
    mood_after_breakdown: Dict[str, int]
    average_mood_shift: float


class ResponseLoopSummaryResponse(BaseModel):
    total_responses: int
    helped_count: int
    average_heard_rating: float


class LecturerReflectionCreate(BaseModel):
    course_id: int
    headline: str = Field(..., min_length=4, max_length=160)
    what_i_heard: str = Field(..., min_length=8, max_length=600)
    what_i_will_change: str = Field(..., min_length=8, max_length=600)


class LecturerReflectionResponse(BaseModel):
    id: int
    course_id: int
    lecturer_name: str
    headline: str
    what_i_heard: str
    what_i_will_change: str
    created_at: datetime
    response_loop_summary: ResponseLoopSummaryResponse


class ResponseLoopCreate(BaseModel):
    reflection_id: int
    helped: bool
    heard_rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class ResponseLoopResponse(BaseModel):
    id: int
    reflection_id: int
    helped: bool
    heard_rating: int
    comment: str | None = None
    created_at: datetime


class RelationshipHealthResponse(BaseModel):
    course_id: int
    course_title: str
    active_reflections: int
    total_feedback: int
    total_response_loops: int
    helpful_response_rate: float
    average_heard_rating: float
    pulse_shift_average: float
    trust_signal: str


class InsightsResponse(BaseModel):
    course_id: int | None = None
    course_title: str | None = None
    total_feedback: int
    sentiment_breakdown: Dict[str, int]
    top_issues: List[str]
    top_strengths: List[str]
    top_recommendations: List[str]
    fair_view: FairViewResponse
    pulse_overview: PulseOverviewResponse
    response_loop_summary: ResponseLoopSummaryResponse
