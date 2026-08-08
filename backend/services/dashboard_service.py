from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.dashboard import DashboardOut, NextModuleOut, RecentInterviewOut
from schemas.profile import ProfileOut, TrackOut
from services import interview_service, profile_service, roadmap_service
from services.progress_service import build_progress, current_phase_index
from services.roadmap_service import RoadmapNotFoundError

_EMPTY_ROADMAP_FIELDS = dict(
    roadmap_summary=None,
    current_phase=None,
    completed_modules=0,
    remaining_modules=0,
    completion_pct=0.0,
    next_module=None,
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


def _recent_interviews_out(db: Session, track_id: int) -> list[RecentInterviewOut]:
    interviews = interview_service.list_interviews(db, track_id, limit=3)
    return [
        RecentInterviewOut(id=i.id, level=i.level, status=i.status, started_at=i.started_at)
        for i in interviews
    ]


def get_dashboard(db: Session) -> DashboardOut:
    user = profile_service.get_profile(db)
    if user is None:
        return DashboardOut(
            profile=None, active_track=None, recent_interviews=[], **_EMPTY_ROADMAP_FIELDS
        )

    profile_out = ProfileOut.model_validate(user)
    active_track = profile_service.get_active_track(db)
    if active_track is None:
        return DashboardOut(
            profile=profile_out,
            active_track=None,
            recent_interviews=[],
            **_EMPTY_ROADMAP_FIELDS,
        )

    track_out = TrackOut.model_validate(active_track)
    recent_interviews = _recent_interviews_out(db, active_track.id)

    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, active_track.id)
    except RoadmapNotFoundError:
        return DashboardOut(
            profile=profile_out,
            active_track=track_out,
            recent_interviews=recent_interviews,
            **_EMPTY_ROADMAP_FIELDS,
        )

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
        recent_interviews=recent_interviews,
    )
