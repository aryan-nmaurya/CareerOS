from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse
from ai.prompts.interview import build_interview_prompt
from ai.prompts.evaluation import build_evaluation_prompt
from models.interview import Interview, InterviewQuestion, ProctoringEvent
from schemas.interview import InterviewOut, InterviewQuestionOut
from services import profile_service, roadmap_service
from services.progress_service import current_phase_index
from services.roadmap_service import RoadmapNotFoundError


class InterviewNotFoundError(Exception):
    pass


class QuestionNotFoundError(Exception):
    pass


class InterviewNotActiveError(Exception):
    pass


_FATAL_EVENT_TYPES = frozenset({"multiple_faces"})
_TERMINATION_WARNING_THRESHOLD = 3


@dataclass(frozen=True)
class EventResult:
    warning_count: int
    should_terminate: bool


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


def list_interviews(db: Session, track_id: int, limit: int = 3) -> list[Interview]:
    return list(
        db.scalars(
            select(Interview)
            .where(Interview.track_id == track_id)
            .order_by(Interview.started_at.desc(), Interview.id.desc())
            .limit(limit)
        )
    )


def list_all_interviews(db: Session, limit: int = 100) -> list[Interview]:
    return list(
        db.scalars(
            select(Interview)
            .order_by(Interview.started_at.desc(), Interview.id.desc())
            .limit(limit)
        )
    )


def complete_interview(
    db: Session, ai_client: AIClient, interview_id: int
) -> Interview:
    interview = get_interview(db, interview_id)
    if interview.status != "active":
        raise InterviewNotActiveError

    items = [
        (q.question, q.expected_points, q.transcript, q.answer_duration_s)
        for q in interview.questions
    ]
    result = ai_client.generate_json(
        build_evaluation_prompt(interview.track.topic, interview.level, items)
    )
    gradings = result.get("questions", [])
    if len(gradings) != len(interview.questions):
        raise AIInvalidResponse(
            f"Expected {len(interview.questions)} interview gradings, got {len(gradings)}"
        )

    for question, grading in zip(interview.questions, gradings):
        question.technical_score = float(grading["technical_score"])
        question.communication_score = float(grading["communication_score"])
        question.confidence_score = float(grading["confidence_score"])
        question.missing_concepts = grading.get("missing_concepts", [])
        question.better_answer = grading.get("better_answer")
        question.feedback = grading.get("feedback", "")

    interview.overall_score = float(result["overall_score"])
    interview.technical_score = float(result["technical_score"])
    interview.communication_score = float(result["communication_score"])
    interview.confidence_score = float(result["confidence_score"])
    interview.strengths = result.get("strengths", [])
    interview.weaknesses = result.get("weaknesses", [])
    interview.recommendations = result.get("recommendations", [])
    interview.summary = result.get("summary", "")
    interview.status = "completed"
    interview.ended_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(interview)
    return interview


def _question_out(question: InterviewQuestion) -> InterviewQuestionOut:
    return InterviewQuestionOut(
        id=question.id,
        order_index=question.order_index,
        question=question.question,
        expected_points=question.expected_points,
        transcript=question.transcript,
        answer_duration_s=question.answer_duration_s,
        technical_score=question.technical_score,
        communication_score=question.communication_score,
        confidence_score=question.confidence_score,
        missing_concepts=question.missing_concepts,
        better_answer=question.better_answer,
        feedback=question.feedback,
    )


def to_interview_out(interview: Interview) -> InterviewOut:
    return InterviewOut(
        id=interview.id,
        track_id=interview.track_id,
        level=interview.level,
        question_count=interview.question_count,
        status=interview.status,
        started_at=interview.started_at,
        ended_at=interview.ended_at,
        termination_reason=interview.termination_reason,
        overall_score=interview.overall_score,
        technical_score=interview.technical_score,
        communication_score=interview.communication_score,
        confidence_score=interview.confidence_score,
        strengths=interview.strengths,
        weaknesses=interview.weaknesses,
        recommendations=interview.recommendations,
        summary=interview.summary,
        questions=[_question_out(q) for q in interview.questions],
    )


def quit_interview(db: Session, interview_id: int) -> Interview:
    interview = get_interview(db, interview_id)
    if interview.status != "active":
        raise InterviewNotActiveError
    interview.status = "terminated"
    interview.termination_reason = "user_quit"
    interview.ended_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(interview)
    return interview


def record_event(db: Session, interview_id: int, event_type: str, detail: str) -> EventResult:
    interview = get_interview(db, interview_id)
    if interview.status != "active":
        raise InterviewNotActiveError

    severity = "fatal" if event_type in _FATAL_EVENT_TYPES else "warning"
    warning_index = None
    if severity == "warning":
        interview.warning_count += 1
        warning_index = interview.warning_count

    should_terminate = severity == "fatal" or interview.warning_count >= _TERMINATION_WARNING_THRESHOLD
    db.add(
        ProctoringEvent(
            interview_id=interview.id,
            type=event_type,
            severity=severity,
            detail=detail,
            warning_index=warning_index,
        )
    )
    if should_terminate:
        interview.status = "terminated"
        interview.termination_reason = "proctoring"
        interview.ended_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return EventResult(interview.warning_count, should_terminate)
