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
