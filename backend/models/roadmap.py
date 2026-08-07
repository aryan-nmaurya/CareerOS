from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from models.user import LearningTrack


class Roadmap(Base):
    """The generated learning path for a track. At most one roadmap matters
    at a time in the UI (the active track's), but nothing here prevents a
    track from accumulating several over time if regenerated."""

    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("learning_tracks.id", ondelete="CASCADE"))
    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_goals: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    final_project: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    track: Mapped["LearningTrack"] = relationship()
    phases: Mapped[list["RoadmapPhase"]] = relationship(
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="RoadmapPhase.order_index",
    )


class RoadmapPhase(Base):
    __tablename__ = "roadmap_phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    roadmap: Mapped["Roadmap"] = relationship(back_populates="phases")
    modules: Mapped[list["RoadmapModule"]] = relationship(
        back_populates="phase",
        cascade="all, delete-orphan",
        order_by="RoadmapModule.order_index",
    )


class RoadmapModule(Base):
    """`kind` distinguishes plain modules from revision checkpoints,
    phase-capping milestones, and mini-projects — the timeline renders each
    differently, but they're all completed the same way (`completed_at`)."""

    __tablename__ = "roadmap_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phase_id: Mapped[int] = mapped_column(ForeignKey("roadmap_phases.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    lessons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    exercises: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    project: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="module")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    phase: Mapped["RoadmapPhase"] = relationship(back_populates="modules")
