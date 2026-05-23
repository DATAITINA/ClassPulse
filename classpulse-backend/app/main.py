import json
import os
from collections import Counter

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import ai, crud, models, schemas
from .db import Base, engine, get_db
from .security import verify_password

load_dotenv()

Base.metadata.create_all(bind=engine)

MOOD_SCORES = {
    "stressed": -2,
    "bored": -1,
    "confused": -1,
    "calm": 0,
    "engaged": 1,
    "excited": 2,
}


def ensure_feedback_columns() -> None:
    inspector = inspect(engine)
    if "feedback" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("feedback")}
    desired_columns = {
        "course_id": "ALTER TABLE feedback ADD COLUMN course_id INTEGER",
        "student_id": "ALTER TABLE feedback ADD COLUMN student_id INTEGER",
        "lecturer_id": "ALTER TABLE feedback ADD COLUMN lecturer_id INTEGER",
        "anonymous_alias": "ALTER TABLE feedback ADD COLUMN anonymous_alias VARCHAR(80)",
        "mood_before": "ALTER TABLE feedback ADD COLUMN mood_before VARCHAR(50)",
        "mood_after": "ALTER TABLE feedback ADD COLUMN mood_after VARCHAR(50)",
        "moderation_status": "ALTER TABLE feedback ADD COLUMN moderation_status VARCHAR(20)",
        "moderation_message": "ALTER TABLE feedback ADD COLUMN moderation_message TEXT",
        "respectful_rewrite": "ALTER TABLE feedback ADD COLUMN respectful_rewrite TEXT",
        "sentiment": "ALTER TABLE feedback ADD COLUMN sentiment VARCHAR(20)",
        "key_issues": "ALTER TABLE feedback ADD COLUMN key_issues TEXT",
        "suggestions": "ALTER TABLE feedback ADD COLUMN suggestions TEXT",
        "strengths": "ALTER TABLE feedback ADD COLUMN strengths TEXT",
        "next_step_ai": "ALTER TABLE feedback ADD COLUMN next_step_ai TEXT",
    }

    missing = [
        statement
        for column_name, statement in desired_columns.items()
        if column_name not in existing_columns
    ]
    if not missing:
        return

    with engine.begin() as conn:
        for statement in missing:
            conn.execute(text(statement))


ensure_feedback_columns()

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


def normalize_mood(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized not in MOOD_SCORES:
        return None
    return normalized


def calculate_average_mood_shift(feedback_list: list[models.Feedback]) -> float:
    total_shift = 0
    shift_count = 0

    for feedback in feedback_list:
        mood_before = normalize_mood(feedback.mood_before)
        mood_after = normalize_mood(feedback.mood_after)
        if not mood_before or not mood_after:
            continue

        total_shift += MOOD_SCORES[mood_after] - MOOD_SCORES[mood_before]
        shift_count += 1

    if not shift_count:
        return 0.0
    return round(total_shift / shift_count, 2)


def minimum_responses_for_fair_view() -> int:
    raw_value = os.getenv("CLASSPULSE_MIN_RESPONSES", "3")
    try:
        return max(1, int(raw_value))
    except ValueError:
        return 3


def serialize_user(user: models.User) -> schemas.UserResponse:
    return schemas.UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        institution=user.institution,
    )


def get_token_from_header(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> str:
    if x_session_token:
        return x_session_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=401, detail="Authentication required")


def get_current_user(
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
) -> models.User:
    user = crud.get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session token")
    return user


def require_role(user: models.User, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="You do not have access to this action")


def serialize_course(db: Session, course: models.Course, viewer: models.User) -> schemas.CourseResponse:
    member_count = crud.get_course_member_count(db, course.id)
    join_code = course.join_code if viewer.role in {"lecturer", "admin"} else None
    return schemas.CourseResponse(
        id=course.id,
        title=course.title,
        code=course.code,
        description=course.description,
        join_code=join_code,
        lecturer_name=course.lecturer.name,
        member_count=member_count,
        created_at=course.created_at,
    )


def build_response_loop_summary(
    responses: list[models.ResponseLoop],
) -> schemas.ResponseLoopSummaryResponse:
    total = len(responses)
    helped_count = sum(1 for item in responses if item.helped)
    avg_rating = round(sum(item.heard_rating for item in responses) / total, 2) if total else 0.0
    return schemas.ResponseLoopSummaryResponse(
        total_responses=total,
        helped_count=helped_count,
        average_heard_rating=avg_rating,
    )


def serialize_reflection(
    reflection: models.LecturerReflection,
) -> schemas.LecturerReflectionResponse:
    summary = build_response_loop_summary(reflection.responses)
    return schemas.LecturerReflectionResponse(
        id=reflection.id,
        course_id=reflection.course_id,
        lecturer_name=reflection.lecturer.name,
        headline=reflection.headline,
        what_i_heard=reflection.what_i_heard,
        what_i_will_change=reflection.what_i_will_change,
        created_at=reflection.created_at,
        response_loop_summary=summary,
    )


def build_trust_signal(
    helpful_rate: float, average_heard_rating: float, pulse_shift_average: float
) -> str:
    if helpful_rate >= 70 and average_heard_rating >= 4:
        return "Trust is growing and students are recognizing the lecturer's response."
    if helpful_rate >= 45 or average_heard_rating >= 3:
        return "Trust is mixed but improving. Keep closing the feedback loop visibly."
    if pulse_shift_average > 0:
        return "Class energy is improving, but students still need stronger signs that they are heard."
    return "Relationship repair needs more visible follow-through and safer, clearer communication."


@app.post("/auth/register", response_model=schemas.AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user = crud.create_user(db, payload)
    session = crud.create_session(db, user)
    return schemas.AuthResponse(token=session.token, user=serialize_user(user))


@app.post("/auth/login", response_model=schemas.AuthResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    session = crud.create_session(db, user)
    return schemas.AuthResponse(token=session.token, user=serialize_user(user))


@app.get("/me", response_model=schemas.UserResponse)
def me(current_user: models.User = Depends(get_current_user)):
    return serialize_user(current_user)


@app.post("/courses", response_model=schemas.CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: schemas.CourseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_role(current_user, "lecturer", "admin")
    course = crud.create_course(db, current_user, payload)
    return serialize_course(db, course, current_user)


@app.post("/courses/join", response_model=schemas.CourseResponse)
def join_course(
    payload: schemas.CourseJoin,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_role(current_user, "student")
    course = crud.get_course_by_join_code(db, payload.join_code)
    if not course:
        raise HTTPException(status_code=404, detail="Join code not found")

    crud.enroll_student(db, course, current_user)
    db.refresh(course)
    return serialize_course(db, course, current_user)


@app.get("/courses", response_model=list[schemas.CourseResponse])
def list_courses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    courses = crud.get_user_courses(db, current_user)
    return [serialize_course(db, course, current_user) for course in courses]


@app.post("/feedback", response_model=schemas.AnalysisResponse)
def submit_feedback(
    payload: schemas.FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_role(current_user, "student")
    course = crud.get_course_for_user(db, current_user, payload.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="You are not enrolled in this course")

    analysis = ai.analyze_feedback(
        payload.feedback_text,
        mood_before=payload.mood_before,
        mood_after=payload.mood_after,
    )

    anonymous_alias = None
    if analysis["accepted"]:
        feedback = crud.create_feedback(db, payload, analysis, course, current_user)
        anonymous_alias = feedback.anonymous_alias

    return schemas.AnalysisResponse(
        accepted=analysis["accepted"],
        moderation_status=analysis["moderation_status"],
        moderation_message=analysis["moderation_message"],
        respectful_rewrite=analysis["respectful_rewrite"],
        anonymous_alias=anonymous_alias,
        sentiment=analysis["sentiment"],
        key_issues=analysis["key_issues"],
        suggestions=analysis["suggestions"],
        strengths=analysis["strengths"],
        next_step_ai=analysis["next_step_ai"],
        pulse_check=schemas.PulseCheckResponse(**analysis["pulse_check"]),
    )


@app.get("/insights", response_model=schemas.InsightsResponse)
def get_insights(
    course_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    courses = crud.get_user_courses(db, current_user)
    if not courses:
        return schemas.InsightsResponse(
            course_id=None,
            course_title=None,
            total_feedback=0,
            sentiment_breakdown={"positive": 0, "negative": 0, "neutral": 0},
            top_issues=[],
            top_strengths=[],
            top_recommendations=[],
            fair_view=schemas.FairViewResponse(
                enough_data=False,
                minimum_responses=minimum_responses_for_fair_view(),
                fairness_note="No course data yet.",
            ),
            pulse_overview=schemas.PulseOverviewResponse(
                mood_before_breakdown={},
                mood_after_breakdown={},
                average_mood_shift=0.0,
            ),
            response_loop_summary=schemas.ResponseLoopSummaryResponse(
                total_responses=0,
                helped_count=0,
                average_heard_rating=0.0,
            ),
        )

    course = None
    if course_id is not None:
        course = crud.get_course_for_user(db, current_user, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not available for this user")
    else:
        course = courses[0]

    feedback_list = crud.get_feedback_for_course(db, course.id)
    total_feedback = len(feedback_list)
    minimum_responses = minimum_responses_for_fair_view()

    sentiment_counts = Counter()
    issue_counts = Counter()
    issue_labels = {}
    strength_counts = Counter()
    strength_labels = {}
    recommendation_counts = Counter()
    recommendation_labels = {}
    mood_before_counts = Counter()
    mood_after_counts = Counter()

    for feedback in feedback_list:
        sentiment = (feedback.sentiment or "neutral").lower().strip()
        if sentiment not in {"positive", "negative", "neutral"}:
            sentiment = "neutral"
        sentiment_counts[sentiment] += 1

        mood_before = normalize_mood(feedback.mood_before)
        if mood_before:
            mood_before_counts[mood_before] += 1

        mood_after = normalize_mood(feedback.mood_after)
        if mood_after:
            mood_after_counts[mood_after] += 1

        for issue in parse_json_list(feedback.key_issues):
            normalized = issue.lower()
            issue_counts[normalized] += 1
            issue_labels.setdefault(normalized, issue)

        for strength in parse_json_list(feedback.strengths):
            normalized = strength.lower()
            strength_counts[normalized] += 1
            strength_labels.setdefault(normalized, strength)

        next_step_ai = (feedback.next_step_ai or "").strip()
        if next_step_ai:
            normalized = next_step_ai.lower()
            recommendation_counts[normalized] += 1
            recommendation_labels.setdefault(normalized, next_step_ai)

    enough_data = total_feedback >= minimum_responses
    if enough_data:
        top_issues = [issue_labels[key] for key, _ in issue_counts.most_common(5)]
        top_strengths = [strength_labels[key] for key, _ in strength_counts.most_common(5)]
        top_recommendations = [
            recommendation_labels[key] for key, _ in recommendation_counts.most_common(3)
        ]
        fairness_note = "Insights are based on repeated patterns rather than isolated comments."
    else:
        top_issues = []
        top_strengths = []
        top_recommendations = []
        fairness_note = (
            f"FairView is holding detailed trends until at least {minimum_responses} "
            "verified responses are collected."
        )

    response_loops = crud.get_response_loops_for_course(db, course.id)
    response_loop_summary = build_response_loop_summary(response_loops)

    return schemas.InsightsResponse(
        course_id=course.id,
        course_title=course.title,
        total_feedback=total_feedback,
        sentiment_breakdown={
            "positive": sentiment_counts.get("positive", 0),
            "negative": sentiment_counts.get("negative", 0),
            "neutral": sentiment_counts.get("neutral", 0),
        },
        top_issues=top_issues,
        top_strengths=top_strengths,
        top_recommendations=top_recommendations,
        fair_view=schemas.FairViewResponse(
            enough_data=enough_data,
            minimum_responses=minimum_responses,
            fairness_note=fairness_note,
        ),
        pulse_overview=schemas.PulseOverviewResponse(
            mood_before_breakdown=dict(mood_before_counts),
            mood_after_breakdown=dict(mood_after_counts),
            average_mood_shift=calculate_average_mood_shift(feedback_list),
        ),
        response_loop_summary=response_loop_summary,
    )


@app.post("/reflections", response_model=schemas.LecturerReflectionResponse, status_code=status.HTTP_201_CREATED)
def create_reflection(
    payload: schemas.LecturerReflectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_role(current_user, "lecturer", "admin")
    course = crud.get_course_for_user(db, current_user, payload.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="You do not manage this course")

    reflection = crud.create_reflection(db, current_user, payload)
    db.refresh(reflection)
    return serialize_reflection(reflection)


@app.get("/reflections", response_model=list[schemas.LecturerReflectionResponse])
def list_reflections(
    course_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    course = crud.get_course_for_user(db, current_user, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not available for this user")

    reflections = crud.get_reflections_for_course(db, course.id)
    return [serialize_reflection(reflection) for reflection in reflections]


@app.post("/response-loops", response_model=schemas.ResponseLoopResponse)
def submit_response_loop(
    payload: schemas.ResponseLoopCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_role(current_user, "student")
    reflection = crud.get_reflection_by_id(db, payload.reflection_id)
    if not reflection:
        raise HTTPException(status_code=404, detail="Reflection not found")

    course = crud.get_course_for_user(db, current_user, reflection.course_id)
    if not course:
        raise HTTPException(status_code=403, detail="You are not enrolled in this course")

    response = crud.upsert_response_loop(db, current_user, reflection, payload)
    return schemas.ResponseLoopResponse(
        id=response.id,
        reflection_id=response.reflection_id,
        helped=response.helped,
        heard_rating=response.heard_rating,
        comment=response.comment,
        created_at=response.created_at,
    )


@app.get("/relationship-health", response_model=schemas.RelationshipHealthResponse)
def relationship_health(
    course_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    course = crud.get_course_for_user(db, current_user, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not available for this user")

    feedback_list = crud.get_feedback_for_course(db, course.id)
    response_loops = crud.get_response_loops_for_course(db, course.id)
    reflections = crud.get_reflections_for_course(db, course.id)

    total_loops = len(response_loops)
    helped_count = sum(1 for item in response_loops if item.helped)
    helpful_rate = round((helped_count / total_loops) * 100, 2) if total_loops else 0.0
    average_heard_rating = (
        round(sum(item.heard_rating for item in response_loops) / total_loops, 2)
        if total_loops
        else 0.0
    )
    pulse_shift_average = calculate_average_mood_shift(feedback_list)

    return schemas.RelationshipHealthResponse(
        course_id=course.id,
        course_title=course.title,
        active_reflections=len(reflections),
        total_feedback=len(feedback_list),
        total_response_loops=total_loops,
        helpful_response_rate=helpful_rate,
        average_heard_rating=average_heard_rating,
        pulse_shift_average=pulse_shift_average,
        trust_signal=build_trust_signal(
            helpful_rate, average_heard_rating, pulse_shift_average
        ),
    )
