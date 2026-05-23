import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas
from .security import generate_join_code, hash_password, new_session_token


def create_user(db: Session, payload: schemas.UserRegister) -> models.User:
    user = models.User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        institution=payload.institution,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email.lower()).first()


def create_session(db: Session, user: models.User) -> models.UserSession:
    session = models.UserSession(user_id=user.id, token=new_session_token())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_user_by_token(db: Session, token: str) -> models.User | None:
    session = (
        db.query(models.UserSession)
        .filter(models.UserSession.token == token)
        .first()
    )
    if not session:
        return None
    return db.query(models.User).filter(models.User.id == session.user_id).first()


def create_course(
    db: Session, lecturer: models.User, payload: schemas.CourseCreate
) -> models.Course:
    join_code = generate_join_code()
    while db.query(models.Course).filter(models.Course.join_code == join_code).first():
        join_code = generate_join_code()

    course = models.Course(
        title=payload.title,
        code=payload.code.upper(),
        description=payload.description,
        join_code=join_code,
        lecturer_id=lecturer.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def get_course_by_join_code(db: Session, join_code: str) -> models.Course | None:
    return (
        db.query(models.Course)
        .filter(models.Course.join_code == join_code.upper().strip())
        .first()
    )


def enroll_student(
    db: Session, course: models.Course, student: models.User
) -> models.Enrollment:
    existing = (
        db.query(models.Enrollment)
        .filter(
            models.Enrollment.course_id == course.id,
            models.Enrollment.student_id == student.id,
        )
        .first()
    )
    if existing:
        return existing

    enrollment = models.Enrollment(course_id=course.id, student_id=student.id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def get_user_courses(db: Session, user: models.User) -> list[models.Course]:
    if user.role in {"lecturer", "admin"}:
        return (
            db.query(models.Course)
            .filter(models.Course.lecturer_id == user.id)
            .order_by(models.Course.created_at.desc())
            .all()
        )

    return (
        db.query(models.Course)
        .join(models.Enrollment, models.Enrollment.course_id == models.Course.id)
        .filter(models.Enrollment.student_id == user.id)
        .order_by(models.Course.created_at.desc())
        .all()
    )


def get_course_member_count(db: Session, course_id: int) -> int:
    return (
        db.query(func.count(models.Enrollment.id))
        .filter(models.Enrollment.course_id == course_id)
        .scalar()
        or 0
    )


def get_course_for_user(
    db: Session, user: models.User, course_id: int
) -> models.Course | None:
    if user.role in {"lecturer", "admin"}:
        return (
            db.query(models.Course)
            .filter(models.Course.id == course_id, models.Course.lecturer_id == user.id)
            .first()
        )

    return (
        db.query(models.Course)
        .join(models.Enrollment, models.Enrollment.course_id == models.Course.id)
        .filter(models.Course.id == course_id, models.Enrollment.student_id == user.id)
        .first()
    )


def generate_anonymous_alias(student: models.User, course: models.Course) -> str:
    number = ((student.id * 17) + (course.id * 7)) % 97 + 1
    return f"Student Echo {number:02d}"


def create_feedback(
    db: Session,
    feedback: schemas.FeedbackCreate,
    analysis: dict[str, Any],
    course: models.Course,
    student: models.User,
) -> models.Feedback:
    alias = generate_anonymous_alias(student, course)
    db_feedback = models.Feedback(
        course_name=course.title,
        lecturer_name=course.lecturer.name,
        feedback_text=feedback.feedback_text,
        course_id=course.id,
        student_id=student.id,
        lecturer_id=course.lecturer_id,
        anonymous_alias=alias,
        mood_before=feedback.mood_before,
        mood_after=feedback.mood_after,
        moderation_status=analysis["moderation_status"],
        moderation_message=analysis["moderation_message"],
        respectful_rewrite=analysis["respectful_rewrite"],
        sentiment=analysis["sentiment"],
        key_issues=json.dumps(analysis["key_issues"]),
        suggestions=json.dumps(analysis["suggestions"]),
        strengths=json.dumps(analysis["strengths"]),
        next_step_ai=analysis["next_step_ai"],
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


def get_feedback_for_course(db: Session, course_id: int) -> list[models.Feedback]:
    return (
        db.query(models.Feedback)
        .filter(models.Feedback.course_id == course_id)
        .order_by(models.Feedback.created_at.desc())
        .all()
    )


def create_reflection(
    db: Session,
    lecturer: models.User,
    payload: schemas.LecturerReflectionCreate,
) -> models.LecturerReflection:
    reflection = models.LecturerReflection(
        course_id=payload.course_id,
        lecturer_id=lecturer.id,
        headline=payload.headline,
        what_i_heard=payload.what_i_heard,
        what_i_will_change=payload.what_i_will_change,
    )
    db.add(reflection)
    db.commit()
    db.refresh(reflection)
    return reflection


def get_reflections_for_course(
    db: Session, course_id: int
) -> list[models.LecturerReflection]:
    return (
        db.query(models.LecturerReflection)
        .filter(models.LecturerReflection.course_id == course_id)
        .order_by(models.LecturerReflection.created_at.desc())
        .all()
    )


def upsert_response_loop(
    db: Session,
    student: models.User,
    reflection: models.LecturerReflection,
    payload: schemas.ResponseLoopCreate,
) -> models.ResponseLoop:
    response = (
        db.query(models.ResponseLoop)
        .filter(
            models.ResponseLoop.reflection_id == reflection.id,
            models.ResponseLoop.student_id == student.id,
        )
        .first()
    )

    if response:
        response.helped = payload.helped
        response.heard_rating = payload.heard_rating
        response.comment = payload.comment
    else:
        response = models.ResponseLoop(
            reflection_id=reflection.id,
            course_id=reflection.course_id,
            student_id=student.id,
            helped=payload.helped,
            heard_rating=payload.heard_rating,
            comment=payload.comment,
        )
        db.add(response)

    db.commit()
    db.refresh(response)
    return response


def get_reflection_by_id(db: Session, reflection_id: int) -> models.LecturerReflection | None:
    return (
        db.query(models.LecturerReflection)
        .filter(models.LecturerReflection.id == reflection_id)
        .first()
    )


def get_response_loops_for_course(db: Session, course_id: int) -> list[models.ResponseLoop]:
    return (
        db.query(models.ResponseLoop)
        .filter(models.ResponseLoop.course_id == course_id)
        .order_by(models.ResponseLoop.created_at.desc())
        .all()
    )
