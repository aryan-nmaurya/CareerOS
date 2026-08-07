from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse, AIUnavailable
from ai.prompts.roadmap import build_roadmap_prompt
from ai.stream_parser import PhaseStreamParser
from models.roadmap import Roadmap, RoadmapModule, RoadmapPhase
from services import assessment_service, profile_service
from services.profile_service import TrackNotFoundError

StreamEvent = tuple[str, dict]


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
