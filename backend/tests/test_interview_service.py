from datetime import datetime

import pytest

from ai.errors import AIInvalidResponse
from schemas.profile import ProfileCreate, TrackCreate
from services import interview_service, profile_service, roadmap_service
from services.interview_service import InterviewNotFoundError, QuestionNotFoundError
from services.profile_service import TrackNotFoundError


def _track(db_session, level="intermediate"):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level=level)
    )


def _generation_response(count=5):
    return {
        "questions": [
            {"question": f"Q{i}?", "expected_points": [f"point-{i}-a", f"point-{i}-b"]}
            for i in range(count)
        ]
    }


_ROADMAP_CHUNKS = [
    '{"title": "Python Roadmap", "summary": "S", "total_weeks": 4, "weekly_hours": 5, ',
    '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
    '"phases": [',
    '{"title": "Foundations", "description": "", "goal": "G", "estimated_hours": 1, "modules": [',
    '{"title": "Variables", "description": "", "lessons": [], "exercises": [], ',
    '"project": null, "estimated_hours": 1, "kind": "module"},',
    '{"title": "Loops", "description": "", "lessons": [], "exercises": [], ',
    '"project": null, "estimated_hours": 1, "kind": "module"}',
    ']}',
    ']}',
]


def test_start_interview_persists_generated_questions(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))

    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    assert interview.status == "active"
    assert interview.track_id == track.id
    assert len(interview.questions) == 5
    assert interview.questions[0].order_index == 0
    assert interview.questions[0].expected_points == ["point-0-a", "point-0-b"]


def test_start_interview_unknown_track_raises(db_session, fake_ai):
    with pytest.raises(TrackNotFoundError):
        interview_service.start_interview(db_session, fake_ai, 999, "intermediate", 5)

    assert fake_ai.calls == []


def test_start_interview_rejects_wrong_question_count(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(3))

    with pytest.raises(AIInvalidResponse):
        interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)


def test_start_interview_is_roadmap_aware_when_roadmap_exists(db_session, fake_ai):
    track = _track(db_session, level="beginner")
    fake_ai.queue_stream(_ROADMAP_CHUNKS)
    list(roadmap_service.stream_roadmap(db_session, fake_ai, track.id))
    roadmap = roadmap_service.get_roadmap_by_track(db_session, track.id)
    roadmap.phases[0].modules[0].completed_at = datetime(2026, 1, 1)
    db_session.commit()

    fake_ai.queue_response(_generation_response(5))
    interview_service.start_interview(db_session, fake_ai, track.id, "beginner", 5)

    prompt_text = fake_ai.calls[-1].user_content
    assert "Variables" in prompt_text
    assert "Loops" in prompt_text


def test_start_interview_without_roadmap_omits_context(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))

    interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    assert "studying" not in fake_ai.calls[-1].user_content.lower()


def test_get_interview_unknown_raises(db_session):
    with pytest.raises(InterviewNotFoundError):
        interview_service.get_interview(db_session, 999)


def test_record_answer_stores_transcript_and_duration(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)
    question = interview.questions[0]

    interview_service.record_answer(
        db_session, interview.id, question.id, "My spoken answer.", 42
    )

    db_session.refresh(question)
    assert question.transcript == "My spoken answer."
    assert question.answer_duration_s == 42


def test_record_answer_unknown_question_raises(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    with pytest.raises(QuestionNotFoundError):
        interview_service.record_answer(db_session, interview.id, 999999, "answer", 10)
