from models.assessment import Assessment, AssessmentQuestion
from models.user import LearningTrack, User
from services import profile_service
from schemas.profile import ProfileCreate, TrackCreate


def _track(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="intermediate")
    )


def test_assessment_and_question_round_trip(db_session):
    track = _track(db_session)

    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()

    mcq = AssessmentQuestion(
        assessment_id=assessment.id,
        order_index=0,
        type="mcq",
        topic_tag="loops",
        question="What does `range(3)` produce?",
        options=["0,1,2", "1,2,3", "0,1,2,3", "1,2"],
        correct_option=0,
    )
    descriptive = AssessmentQuestion(
        assessment_id=assessment.id,
        order_index=1,
        type="descriptive",
        topic_tag="oop",
        question="Explain inheritance.",
        expected_points=["base class", "override", "super()"],
    )
    db_session.add_all([mcq, descriptive])
    db_session.commit()

    assert len(assessment.questions) == 2
    # order_by="AssessmentQuestion.order_index" keeps them in question order
    assert [q.order_index for q in assessment.questions] == [0, 1]
    assert assessment.track.topic == "Python"


def test_deleting_track_cascades_to_assessment(db_session):
    track = _track(db_session)
    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()
    assessment_id = assessment.id

    db_session.delete(db_session.get(LearningTrack, track.id))
    db_session.commit()

    assert db_session.get(Assessment, assessment_id) is None


def test_deleting_assessment_cascades_to_questions(db_session):
    track = _track(db_session)
    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()

    question = AssessmentQuestion(
        assessment_id=assessment.id,
        order_index=0,
        type="mcq",
        topic_tag="loops",
        question="...",
        options=["a", "b", "c", "d"],
        correct_option=1,
    )
    db_session.add(question)
    db_session.commit()
    question_id = question.id

    db_session.delete(assessment)
    db_session.commit()

    assert db_session.get(AssessmentQuestion, question_id) is None
