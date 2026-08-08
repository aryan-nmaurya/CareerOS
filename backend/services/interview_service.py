from __future__ import annotations

from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse
from ai.prompts.interview import build_interview_prompt
from models.interview import Interview, InterviewQuestion
from services import profile_service, roadmap_service
from services.progress_service import current_phase_index
from services.roadmap_service import RoadmapNotFoundError


class InterviewNotFoundError(Exception):
    pass


class QuestionNotFoundError(Exception):
    pass


def _roadmap_context(roadmap) -> list[str] | None:
    titles: list[str] = []
    for phase in roadmap.phases:
        for module in phase.modules:
            if module.completed_at is not None:
                titles.append(module.title)
    if roadmap.phases:
        current = current_phase_index(roadmap.phases)
        titles.extend(m.title for m in roadmap.phases[current].modules)

    seen: set[str] = set()
    deduped: list[str] = []
    for title in titles:
        if title not in seen:
            seen.add(title)
            deduped.append(title)
    return deduped or None


def start_interview(
    db: Session, ai_client: AIClient, track_id: int, level: str, question_count: int
) -> Interview:
    track = profile_service.get_track(db, track_id)

    roadmap_context = None
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, track.id)
        roadmap_context = _roadmap_context(roadmap)
    except RoadmapNotFoundError:
        pass

    prompt = build_interview_prompt(track.topic, level, question_count, roadmap_context)
    result = ai_client.generate_json(prompt)
    questions_data = result.get("questions", [])
    if len(questions_data) != question_count:
        raise AIInvalidResponse(
            f"Expected {question_count} questions, got {len(questions_data)}"
        )

    interview = Interview(
        track_id=track.id, level=level, question_count=question_count, status="active"
    )
    db.add(interview)
    db.flush()

    for index, q in enumerate(questions_data):
        db.add(
            InterviewQuestion(
                interview_id=interview.id,
                order_index=index,
                question=q["question"],
                expected_points=q.get("expected_points", []),
            )
        )

    db.commit()
    db.refresh(interview)
    return interview


def get_interview(db: Session, interview_id: int) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise InterviewNotFoundError
    return interview


def record_answer(
    db: Session, interview_id: int, question_id: int, transcript: str, duration_s: int
) -> None:
    interview = get_interview(db, interview_id)
    question = next((q for q in interview.questions if q.id == question_id), None)
    if question is None:
        raise QuestionNotFoundError

    question.transcript = transcript
    question.answer_duration_s = duration_s
    db.commit()
