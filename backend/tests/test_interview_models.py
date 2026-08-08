from models.interview import Interview, InterviewQuestion
from models.user import LearningTrack
from schemas.profile import ProfileCreate, TrackCreate
from services import profile_service


def _track(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="intermediate")
    )


def test_interview_question_round_trip(db_session):
    track = _track(db_session)

    interview = Interview(
        track_id=track.id, level="intermediate", question_count=8, status="active"
    )
    db_session.add(interview)
    db_session.commit()

    question = InterviewQuestion(
        interview_id=interview.id,
        order_index=0,
        question="Explain the GIL.",
        expected_points=["single lock", "affects CPU-bound threads"],
    )
    db_session.add(question)
    db_session.commit()

    assert interview.questions == [question]
    assert question.interview is interview
    assert question.transcript is None
    assert question.answer_duration_s is None
    assert interview.track.id == track.id
    assert interview.warning_count == 0
    assert interview.overall_score is None


def test_deleting_track_cascades_to_interviews_and_questions(db_session):
    track = _track(db_session)
    interview = Interview(track_id=track.id, level="intermediate", question_count=5, status="active")
    db_session.add(interview)
    db_session.commit()
    question = InterviewQuestion(
        interview_id=interview.id, order_index=0, question="Q", expected_points=["p"]
    )
    db_session.add(question)
    db_session.commit()
    interview_id, question_id = interview.id, question.id

    db_session.delete(db_session.get(LearningTrack, track.id))
    db_session.commit()

    assert db_session.get(Interview, interview_id) is None
    assert db_session.get(InterviewQuestion, question_id) is None


def test_status_and_termination_fields(db_session):
    track = _track(db_session)
    interview = Interview(
        track_id=track.id,
        level="intermediate",
        question_count=5,
        status="terminated",
        termination_reason="user_quit",
    )
    db_session.add(interview)
    db_session.commit()

    assert interview.status == "terminated"
    assert interview.termination_reason == "user_quit"
    assert interview.ended_at is None
