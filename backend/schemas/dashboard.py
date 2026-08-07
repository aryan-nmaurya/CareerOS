from pydantic import BaseModel

from schemas.profile import ProfileOut, TrackOut


class NextModuleOut(BaseModel):
    id: int
    title: str
    kind: str
    phase_title: str


class DashboardOut(BaseModel):
    profile: ProfileOut | None
    active_track: TrackOut | None
    roadmap_summary: str | None
    current_phase: str | None
    completed_modules: int
    remaining_modules: int
    completion_pct: float
    next_module: NextModuleOut | None
    recent_interviews: list = []
