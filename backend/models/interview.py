from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from models.user import LearningTrack


class Interview(Base):
    """One mock interview attempt for a track. Score/strengths/weaknesses/
    recommendations/summary all stay NULL until Plan 5's evaluation step —
    Plan 4 only generates questions and captures transcripts."""

    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("learning_tracks.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    communication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    track: Mapped["LearningTrack"] = relationship()
    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.order_index",
    )


class InterviewQuestion(Base):
    """transcript/answer_duration_s are Plan 4's capture fields, written by
    record_answer. The four score-ish columns after them stay NULL until
    Plan 5's evaluation call."""

    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_points: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    communication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_concepts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    better_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="questions")
