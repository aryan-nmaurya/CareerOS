from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse, AIUnavailable
from ai.prompts.roadmap import build_roadmap_prompt
from ai.stream_parser import PhaseStreamParser
from models.roadmap import Roadmap, RoadmapModule, RoadmapPhase
from schemas.roadmap import (
    ModuleToggleOut,
    ProgressOut,
    RoadmapModuleOut,
    RoadmapOut,
    RoadmapPhaseOut,
)
from services import assessment_service, profile_service
from services.profile_service import TrackNotFoundError
from services.progress_service import build_progress

StreamEvent = tuple[str, dict]


class RoadmapNotFoundError(Exception):
    pass


class ModuleNotFoundError(Exception):
    pass


def stream_roadmap(db: Session, ai_client: AIClient, track_id: int) -> Iterator[StreamEvent]:
    """Drives PhaseStreamParser over a live Gemini stream, persisting
    Roadmap/RoadmapPhase/RoadmapModule rows as events arrive inside one
    uncommitted transaction. Commits once, only if at least one phase
    actually arrived; rolls back on any AI failure or an empty result.
    Yields SSE-ready (event, data) tuples — the router owns HTTP framing.
    """
    try:
        track = profile_service.get_track(db, track_id)
    except TrackNotFoundError:
        yield ("error", {"code": "track_not_found", "message": "That learning track does not exist."})
        return

    assessment = None
    if track.experience_level != "beginner":
        assessment = assessment_service.get_latest_completed_assessment(db, track.id)

    prompt = build_roadmap_prompt(track.topic, track.experience_level, assessment)
    parser = PhaseStreamParser()
    roadmap: Roadmap | None = None
    phase_count = 0

    try:
        for chunk in ai_client.generate_json_stream(prompt):
            for event, data in parser.feed(chunk):
                if event == "meta":
                    roadmap = Roadmap(
                        track_id=track.id,
                        assessment_id=assessment.id if assessment else None,
                        title=data["title"],
                        summary=data["summary"],
                        total_weeks=data["total_weeks"],
                        weekly_hours=data["weekly_hours"],
                        weekly_goals=data.get("weekly_goals", []),
                        final_project=data.get("final_project"),
                    )
                    db.add(roadmap)
                    db.flush()
                    yield ("meta", data)
                elif event == "phase":
                    if roadmap is None:
                        db.rollback()
                        yield (
                            "error",
                            {
                                "code": "ai_invalid_response",
                                "message": "Phase arrived before roadmap metadata.",
                            },
                        )
                        return
                    phase = RoadmapPhase(
                        roadmap_id=roadmap.id,
                        order_index=phase_count,
                        title=data["title"],
                        description=data.get("description", ""),
                        goal=data["goal"],
                        estimated_hours=data.get("estimated_hours", 0),
                    )
                    db.add(phase)
                    db.flush()
                    for m_index, module in enumerate(data.get("modules", [])):
                        db.add(
                            RoadmapModule(
                                phase_id=phase.id,
                                order_index=m_index,
                                title=module["title"],
                                description=module.get("description", ""),
                                lessons=module.get("lessons", []),
                                exercises=module.get("exercises", []),
                                project=module.get("project"),
                                estimated_hours=module.get("estimated_hours", 0),
                                kind=module.get("kind", "module"),
                            )
                        )
                    phase_count += 1
                    yield (
                        "phase",
                        {
                            "order_index": phase.order_index,
                            "title": phase.title,
                            "modules": data.get("modules", []),
                        },
                    )
    except AIUnavailable as exc:
        db.rollback()
        yield ("error", {"code": "ai_unavailable", "message": str(exc)})
        return
    except AIInvalidResponse as exc:
        db.rollback()
        yield ("error", {"code": "ai_invalid_response", "message": str(exc)})
        return

    if roadmap is None or phase_count == 0:
        db.rollback()
        yield ("error", {"code": "ai_invalid_response", "message": "No phases were generated."})
        return

    db.commit()
    yield ("done", {"roadmap_id": roadmap.id})


def get_roadmap_by_track(db: Session, track_id: int) -> Roadmap:
    roadmap = db.scalars(
        select(Roadmap)
        .where(Roadmap.track_id == track_id)
        .order_by(Roadmap.created_at.desc(), Roadmap.id.desc())
    ).first()
    if roadmap is None:
        raise RoadmapNotFoundError
    return roadmap


def get_module(db: Session, module_id: int) -> RoadmapModule:
    module = db.get(RoadmapModule, module_id)
    if module is None:
        raise ModuleNotFoundError
    return module


def toggle_module(db: Session, module_id: int, completed: bool) -> RoadmapModule:
    module = get_module(db, module_id)
    if completed:
        if module.completed_at is None:
            now = datetime.now(UTC).replace(tzinfo=None)
            module.completed_at = now
            if module.started_at is None:
                module.started_at = now
    else:
        # started_at is left alone on purpose — un-completing shouldn't erase
        # that the learner did start it at some point.
        module.completed_at = None
    db.commit()
    db.refresh(module)
    return module


def to_module_out(module: RoadmapModule) -> RoadmapModuleOut:
    return RoadmapModuleOut(
        id=module.id,
        order_index=module.order_index,
        title=module.title,
        description=module.description,
        lessons=module.lessons,
        exercises=module.exercises,
        project=module.project,
        estimated_hours=module.estimated_hours,
        kind=module.kind,
        started_at=module.started_at,
        completed_at=module.completed_at,
    )


def to_phase_out(phase: RoadmapPhase) -> RoadmapPhaseOut:
    return RoadmapPhaseOut(
        id=phase.id,
        order_index=phase.order_index,
        title=phase.title,
        description=phase.description,
        goal=phase.goal,
        estimated_hours=phase.estimated_hours,
        modules=[to_module_out(m) for m in phase.modules],
    )


def to_roadmap_out(roadmap: Roadmap) -> RoadmapOut:
    return RoadmapOut(
        id=roadmap.id,
        track_id=roadmap.track_id,
        title=roadmap.title,
        summary=roadmap.summary,
        total_weeks=roadmap.total_weeks,
        weekly_hours=roadmap.weekly_hours,
        weekly_goals=roadmap.weekly_goals,
        final_project=roadmap.final_project,
        created_at=roadmap.created_at,
        phases=[to_phase_out(p) for p in roadmap.phases],
        progress=ProgressOut(**build_progress(roadmap.phases)),
    )


def to_module_toggle_out(module: RoadmapModule) -> ModuleToggleOut:
    progress = build_progress(module.phase.roadmap.phases)
    return ModuleToggleOut(module=to_module_out(module), progress=ProgressOut(**progress))
