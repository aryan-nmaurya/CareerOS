import pytest

from ai.client import Prompt
from ai.errors import AIInvalidResponse
from schemas.profile import ProfileCreate, TrackCreate
from services import assessment_service, profile_service
from services.assessment_service import (
    AssessmentNotApplicableError,
    AssessmentNotFoundError,
    QuestionNotFoundError,
)
from schemas.assessment import AnswerSave


def _track(db_session, level="intermediate"):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level=level)
    )


def _generation_response(count=8):
    questions = []
    for i in range(count):
        if i % 2 == 0:
            questions.append(
                {
                    "type": "mcq",
                    "topic_tag": f"tag{i}",
                    "question": f"Q{i}?",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 1,
                }
            )
        else:
            questions.append(
                {
                    "type": "descriptive",
                    "topic_tag": f"tag{i}",
                    "question": f"Q{i}?",
                    "expected_points": ["point a", "point b"],
                }
            )
    return {"questions": questions}


def test_start_assessment_persists_generated_questions(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))

    assessment = assessment_service.start_assessment(db_session, fake_ai, track.id)

    assert assessment.status == "in_progress"
    assert len(assessment.questions) == 8
    assert assessment.questions[0].order_index == 0
    assert fake_ai.calls[0].user_content.find("Python") != -1


def test_start_assessment_rejects_beginner_track(db_session, fake_ai):
    track = _track(db_session, level="beginner")

    with pytest.raises(AssessmentNotApplicableError):
        assessment_service.start_assessment(db_session, fake_ai, track.id)

    assert fake_ai.calls == []


def test_start_assessment_rejects_out_of_range_question_count(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(3))

    with pytest.raises(AIInvalidResponse):
        assessment_service.start_assessment(db_session, fake_ai, track.id)


def test_get_assessment_unknown_raises(db_session):
    with pytest.raises(AssessmentNotFoundError):
        assessment_service.get_assessment(db_session, 4242)


def test_list_assessments_orders_most_recent_first(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    first = assessment_service.start_assessment(db_session, fake_ai, track.id)
    fake_ai.queue_response(_generation_response(8))
    second = assessment_service.start_assessment(db_session, fake_ai, track.id)

    listed = assessment_service.list_assessments(db_session)

    assert [a.id for a in listed] == [second.id, first.id]


def test_save_answer_stores_the_answer(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    assessment = assessment_service.start_assessment(db_session, fake_ai, track.id)
    question = assessment.questions[0]

    assessment_service.save_answer(
        db_session, assessment.id, AnswerSave(question_id=question.id, answer="1")
    )

    db_session.refresh(question)
    assert question.user_answer == "1"


def test_save_answer_unknown_question_raises(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    assessment = assessment_service.start_assessment(db_session, fake_ai, track.id)

    with pytest.raises(QuestionNotFoundError):
        assessment_service.save_answer(
            db_session, assessment.id, AnswerSave(question_id=999999, answer="x")
        )


from models.assessment import AssessmentQuestion
from services.assessment_service import (
    AssessmentAlreadySubmittedError,
    band_level,
    group_by_topic,
    score_mcq_question,
)


# ── score_mcq_question — pure ────────────────────────────────────────────


def _mcq(user_answer=None, correct_option=1, options=("a", "b", "c", "d")):
    return AssessmentQuestion(
        type="mcq",
        topic_tag="x",
        question="q",
        options=list(options),
        correct_option=correct_option,
        user_answer=user_answer,
    )


def test_score_mcq_correct_answer():
    question = _mcq(user_answer="1", correct_option=1)

    score_mcq_question(question)

    assert question.score == 10.0
    assert question.ai_feedback == "Correct."


def test_score_mcq_incorrect_answer_names_the_right_option():
    question = _mcq(user_answer="0", correct_option=1, options=("a", "b", "c", "d"))

    score_mcq_question(question)

    assert question.score == 0.0
    assert "b" in question.ai_feedback


def test_score_mcq_unanswered():
    question = _mcq(user_answer=None)

    score_mcq_question(question)

    assert question.score == 0.0
    assert question.ai_feedback == "Not answered."


def test_score_mcq_malformed_answer_scores_zero_without_crashing():
    question = _mcq(user_answer="not-a-number")

    score_mcq_question(question)

    assert question.score == 0.0


# ── band_level — pure ─────────────────────────────────────────────────────


def test_band_level_boundaries():
    assert band_level(39) == "foundational"
    assert band_level(40) == "intermediate"
    assert band_level(69) == "intermediate"
    assert band_level(70) == "advanced"


# ── group_by_topic — pure ────────────────────────────────────────────────


def test_group_by_topic_strengths_and_weaknesses():
    def q(tag, score):
        question = _mcq()
        question.topic_tag = tag
        question.score = score
        return question

    questions = [
        q("loops", 8),
        q("loops", 9),  # mean 8.5 -> strength
        q("oop", 3),
        q("oop", 2),  # mean 2.5 -> weakness
        q("files", 5),  # mean 5 -> neither
    ]

    strengths, weaknesses = group_by_topic(questions)

    assert strengths == ["loops"]
    assert weaknesses == ["oop"]


# ── submit_assessment — orchestration ────────────────────────────────────


def _start_with_mix(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(
        {
            "questions": [
                {
                    "type": "mcq",
                    "topic_tag": "loops",
                    "question": "Q0",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 1,
                },
                {
                    "type": "descriptive",
                    "topic_tag": "oop",
                    "question": "Explain inheritance.",
                    "expected_points": ["base class", "override"],
                },
                *[
                    {
                        "type": "mcq",
                        "topic_tag": f"tag{i}",
                        "question": f"Q{i}",
                        "options": ["a", "b", "c", "d"],
                        "correct_option": 0,
                    }
                    for i in range(6)
                ],
            ]
        }
    )
    return assessment_service.start_assessment(db_session, fake_ai, track.id)


def test_submit_scores_mcq_and_grades_descriptive_via_one_ai_call(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    mcq_question = assessment.questions[0]
    descriptive_question = assessment.questions[1]

    assessment_service.save_answer(
        db_session, assessment.id, AnswerSave(question_id=mcq_question.id, answer="1")
    )
    assessment_service.save_answer(
        db_session,
        assessment.id,
        AnswerSave(
            question_id=descriptive_question.id,
            answer="A subclass extends a base class and can override methods.",
        ),
    )
    for question in assessment.questions[2:]:
        assessment_service.save_answer(
            db_session, assessment.id, AnswerSave(question_id=question.id, answer="0")
        )

    fake_ai.queue_response(
        {
            "gradings": [{"score": 9.0, "feedback": "Strong answer covering both points."}],
            "summary": "Solid grasp of OOP fundamentals.",
        }
    )

    result = assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.summary == "Solid grasp of OOP fundamentals."
    # 8 questions, 7 correct mcq (score 10) + 1 descriptive (score 9) = mean 9.875 * 10
    assert result.score == pytest.approx(98.75, abs=0.1)
    assert result.estimated_level == "advanced"
    # Grading call only covered the one descriptive question, not all 8.
    grading_call = fake_ai.calls[-1]
    assert grading_call.user_content.count("Question ") == 1


def test_submit_skips_ai_call_when_no_descriptive_answers_given(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    # Answer nothing at all.

    calls_before = len(fake_ai.calls)
    result = assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    assert len(fake_ai.calls) == calls_before  # no grading call was made
    assert result.status == "completed"
    assert result.score == 0.0
    assert result.summary == "Assessment completed."


def test_submit_twice_raises(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    fake_ai.queue_response({"gradings": [], "summary": "done"})
    # No descriptive answers given, so no grading call is actually made —
    # queue is harmless leftover, submit still succeeds on the mcq-only path.
    assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    with pytest.raises(AssessmentAlreadySubmittedError):
        assessment_service.submit_assessment(db_session, fake_ai, assessment.id)


def test_save_answer_after_submit_raises(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    with pytest.raises(AssessmentAlreadySubmittedError):
        assessment_service.save_answer(
            db_session,
            assessment.id,
            AnswerSave(question_id=assessment.questions[0].id, answer="1"),
        )
