from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse
from ai.prompts.assessment import build_generation_prompt, build_grading_prompt
from models.assessment import Assessment, AssessmentQuestion
from schemas.assessment import AnswerSave, AssessmentOut, AssessmentQuestionOut
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


def get_latest_completed_assessment(db: Session, track_id: int) -> Assessment | None:
    return db.scalars(
        select(Assessment)
        .where(Assessment.track_id == track_id, Assessment.status == "completed")
        .order_by(Assessment.started_at.desc(), Assessment.id.desc())
    ).first()


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


def score_mcq_question(question: AssessmentQuestion) -> None:
    """Mutates question.score and question.ai_feedback in place."""
    if question.user_answer is None:
        question.score = 0.0
        question.ai_feedback = "Not answered."
        return

    try:
        selected = int(question.user_answer)
    except ValueError:
        selected = None

    if selected == question.correct_option:
        question.score = 10.0
        question.ai_feedback = "Correct."
    else:
        correct_text = question.options[question.correct_option]
        question.score = 0.0
        question.ai_feedback = f"Incorrect. The correct answer was: {correct_text}"


def band_level(score: float) -> str:
    if score < 40:
        return "foundational"
    if score < 70:
        return "intermediate"
    return "advanced"


def group_by_topic(questions: list[AssessmentQuestion]) -> tuple[list[str], list[str]]:
    """Groups scored questions by topic_tag; mean >= 7 is a strength,
    mean <= 4 is a weakness, otherwise the tag is neither."""
    by_tag: dict[str, list[float]] = defaultdict(list)
    for question in questions:
        by_tag[question.topic_tag].append(question.score)

    strengths: list[str] = []
    weaknesses: list[str] = []
    for tag, scores in by_tag.items():
        mean = sum(scores) / len(scores)
        if mean >= 7:
            strengths.append(tag)
        elif mean <= 4:
            weaknesses.append(tag)
    return strengths, weaknesses


def submit_assessment(db: Session, ai_client: AIClient, assessment_id: int) -> Assessment:
    assessment = get_assessment(db, assessment_id)
    if assessment.status == "completed":
        raise AssessmentAlreadySubmittedError

    descriptive_to_grade: list[AssessmentQuestion] = []

    for question in assessment.questions:
        if question.type == "mcq":
            score_mcq_question(question)
        elif question.user_answer and question.user_answer.strip():
            descriptive_to_grade.append(question)
        else:
            question.score = 0.0
            question.ai_feedback = "Not answered."

    summary = "Assessment completed."
    if descriptive_to_grade:
        prompt = build_grading_prompt(
            assessment.track.topic,
            [
                (q.question, q.expected_points, q.user_answer)
                for q in descriptive_to_grade
            ],
        )
        result = ai_client.generate_json(prompt)
        gradings = result.get("gradings", [])
        if len(gradings) != len(descriptive_to_grade):
            raise AIInvalidResponse(
                f"Expected {len(descriptive_to_grade)} gradings, got {len(gradings)}"
            )
        for question, grading in zip(descriptive_to_grade, gradings):
            question.score = float(grading["score"])
            question.ai_feedback = grading["feedback"]
        summary = result.get("summary", summary)

    all_scores = [q.score for q in assessment.questions]
    final_score = (sum(all_scores) / len(all_scores)) * 10 if all_scores else 0.0

    assessment.score = round(final_score, 1)
    assessment.estimated_level = band_level(final_score)
    assessment.strengths, assessment.weaknesses = group_by_topic(assessment.questions)
    assessment.summary = summary
    assessment.status = "completed"
    # naive on purpose: the DateTime column isn't timezone-aware, and
    # started_at (from SQLite's func.now()) is naive too — keeping both
    # naive avoids mixing aware/naive datetimes on the same row.
    assessment.completed_at = datetime.now(UTC).replace(tzinfo=None)

    db.commit()
    db.refresh(assessment)
    return assessment


def _question_out(question: AssessmentQuestion, reveal: bool) -> AssessmentQuestionOut:
    return AssessmentQuestionOut(
        id=question.id,
        order_index=question.order_index,
        type=question.type,
        topic_tag=question.topic_tag,
        question=question.question,
        options=question.options,
        correct_option=question.correct_option if reveal else None,
        expected_points=question.expected_points if reveal else None,
        user_answer=question.user_answer,
        score=question.score,
        ai_feedback=question.ai_feedback,
    )


def to_assessment_out(assessment: Assessment) -> AssessmentOut:
    """The only place that decides what a client is allowed to see. Options
    (the 4 mcq choices) are always visible — a question is unanswerable
    without them. The answer key (correct_option, expected_points) is only
    revealed once the assessment is completed."""
    reveal = assessment.status == "completed"
    return AssessmentOut(
        id=assessment.id,
        track_id=assessment.track_id,
        level=assessment.level,
        status=assessment.status,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        score=assessment.score,
        estimated_level=assessment.estimated_level,
        strengths=assessment.strengths,
        weaknesses=assessment.weaknesses,
        summary=assessment.summary,
        questions=[_question_out(q, reveal) for q in assessment.questions],
    )
