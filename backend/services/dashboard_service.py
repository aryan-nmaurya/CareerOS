from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.dashboard import DashboardOut, NextModuleOut
from schemas.profile import ProfileOut, TrackOut
from services import profile_service, roadmap_service
from services.progress_service import build_progress, current_phase_index
from services.roadmap_service import RoadmapNotFoundError

_EMPTY = dict(
    roadmap_summary=None,
    current_phase=None,
    completed_modules=0,
    remaining_modules=0,
    completion_pct=0.0,
    next_module=None,
    recent_interviews=[],
)


def _find_next_module(phases) -> NextModuleOut | None:
    if not phases:
        return None
    phase = phases[current_phase_index(phases)]
    for module in phase.modules:
        if module.completed_at is None:
            return NextModuleOut(
                id=module.id, title=module.title, kind=module.kind, phase_title=phase.title
            )
    return None


def get_dashboard(db: Session) -> DashboardOut:
    user = profile_service.get_profile(db)
    if user is None:
        return DashboardOut(profile=None, active_track=None, **_EMPTY)

    profile_out = ProfileOut.model_validate(user)
    active_track = profile_service.get_active_track(db)
    if active_track is None:
        return DashboardOut(profile=profile_out, active_track=None, **_EMPTY)

    track_out = TrackOut.model_validate(active_track)
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, active_track.id)
    except RoadmapNotFoundError:
        return DashboardOut(profile=profile_out, active_track=track_out, **_EMPTY)

    progress = build_progress(roadmap.phases)
    return DashboardOut(
        profile=profile_out,
        active_track=track_out,
        roadmap_summary=roadmap.summary,
        current_phase=progress["current_phase_title"],
        completed_modules=progress["completed_modules"],
        remaining_modules=progress["total_modules"] - progress["completed_modules"],
        completion_pct=progress["completion_pct"],
        next_module=_find_next_module(roadmap.phases),
        recent_interviews=[],
    )
