from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoadmapModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    description: str
    lessons: list[str]
    exercises: list[str]
    project: dict | None
    estimated_hours: int
    kind: str
    started_at: datetime | None
    completed_at: datetime | None


class RoadmapPhaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    description: str
    goal: str
    estimated_hours: int
    modules: list[RoadmapModuleOut]


class PhaseProgressOut(BaseModel):
    order_index: int
    completion_pct: float
    unlocked: bool


class ProgressOut(BaseModel):
    completion_pct: float
    completed_modules: int
    total_modules: int
    current_phase_index: int
    current_phase_title: str | None
    phases: list[PhaseProgressOut]


class RoadmapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    title: str
    summary: str
    total_weeks: int
    weekly_hours: int
    weekly_goals: list[dict]
    final_project: dict | None
    created_at: datetime
    phases: list[RoadmapPhaseOut]
    progress: ProgressOut


class ModuleToggle(BaseModel):
    completed: bool


class ModuleToggleOut(BaseModel):
    module: RoadmapModuleOut
    progress: ProgressOut
