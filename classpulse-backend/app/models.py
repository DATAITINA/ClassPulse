from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owned_courses = relationship("Course", back_populates="lecturer")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    join_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lecturer = relationship("User", back_populates="owned_courses")
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    reflections = relationship(
        "LecturerReflection", back_populates="course", cascade="all, delete-orphan"
    )


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_enrollment_course_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course = relationship("Course", back_populates="enrollments")
    student = relationship("User")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    lecturer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    course_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    student_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    lecturer_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    anonymous_alias: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mood_before: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mood_after: Mapped[str | None] = mapped_column(String(50), nullable=True)
    moderation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    moderation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    respectful_rewrite: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    key_issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_step_ai: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LecturerReflection(Base):
    __tablename__ = "lecturer_reflections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    headline: Mapped[str] = mapped_column(String(160), nullable=False)
    what_i_heard: Mapped[str] = mapped_column(Text, nullable=False)
    what_i_will_change: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="reflections")
    lecturer = relationship("User")
    responses = relationship(
        "ResponseLoop", back_populates="reflection", cascade="all, delete-orphan"
    )


class ResponseLoop(Base):
    __tablename__ = "response_loops"
    __table_args__ = (
        UniqueConstraint("reflection_id", "student_id", name="uq_response_reflection_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reflection_id: Mapped[int] = mapped_column(
        ForeignKey("lecturer_reflections.id"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    helped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    heard_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    reflection = relationship("LecturerReflection", back_populates="responses")
