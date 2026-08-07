from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse
from ai.prompts.assessment import build_generation_prompt
from models.assessment import Assessment, AssessmentQuestion
from schemas.assessment import AnswerSave
from services import profile_service


class AssessmentNotApplicableError(Exception):
    """Beginner tracks skip assessment entirely."""


class AssessmentNotFoundError(Exception):
    pass


class QuestionNotFoundError(Exception):
    pass


class AssessmentAlreadySubmittedError(Exception):
    pass


def start_assessment(db: Session, ai_client: AIClient, track_id: int) -> Assessment:
    track = profile_service.get_track(db, track_id)
    if track.experience_level == "beginner":
        raise AssessmentNotApplicableError

    prompt = build_generation_prompt(track.topic, track.experience_level)
    result = ai_client.generate_json(prompt)
    questions_data = result.get("questions", [])
    if not (8 <= len(questions_data) <= 12):
        raise AIInvalidResponse(f"Expected 8-12 questions, got {len(questions_data)}")

    assessment = Assessment(
        track_id=track.id, level=track.experience_level, status="in_progress"
    )
    db.add(assessment)
    db.flush()  # assigns assessment.id so the child rows below can reference it

    for index, q in enumerate(questions_data):
        db.add(
            AssessmentQuestion(
                assessment_id=assessment.id,
                order_index=index,
                type=q["type"],
                topic_tag=q["topic_tag"],
                question=q["question"],
                options=q.get("options"),
                correct_option=q.get("correct_option"),
                expected_points=q.get("expected_points"),
            )
        )

    db.commit()
    db.refresh(assessment)
    return assessment


def get_assessment(db: Session, assessment_id: int) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise AssessmentNotFoundError
    return assessment


def list_assessments(db: Session) -> list[Assessment]:
    # id as a tiebreak: SQLite's func.now() has second-level resolution, so
    # two assessments started within the same second would otherwise tie
    # and sort unpredictably.
    return list(
        db.scalars(
            select(Assessment).order_by(Assessment.started_at.desc(), Assessment.id.desc())
        )
    )


def save_answer(db: Session, assessment_id: int, payload: AnswerSave) -> None:
    assessment = get_assessment(db, assessment_id)
    if assessment.status == "completed":
        raise AssessmentAlreadySubmittedError

    question = next(
        (q for q in assessment.questions if q.id == payload.question_id), None
    )
    if question is None:
        raise QuestionNotFoundError

    question.user_answer = payload.answer
    db.commit()
