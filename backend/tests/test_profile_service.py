from models.user import LearningTrack, User


def test_foreign_keys_are_enforced(db_session):
    """SQLite silently ignores FK constraints unless PRAGMA foreign_keys=ON is set."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    orphan = LearningTrack(user_id=999, topic="Python", experience_level="beginner")
    db_session.add(orphan)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_and_track_round_trip(db_session):
    user = User(name="Aryan")
    db_session.add(user)
    db_session.commit()

    track = LearningTrack(user_id=user.id, topic="Python", experience_level="beginner")
    db_session.add(track)
    db_session.commit()

    assert track.id is not None
    assert track.is_active is True
    assert user.tracks == [track]


import pytest

from schemas.profile import ProfileCreate, ProfileUpdate
from services import profile_service
from services.profile_service import ProfileExistsError, ProfileNotFoundError


def test_get_profile_returns_none_when_not_onboarded(db_session):
    assert profile_service.get_profile(db_session) is None


def test_create_profile_trims_whitespace(db_session):
    user = profile_service.create_profile(db_session, ProfileCreate(name="  Aryan  "))

    assert user.name == "Aryan"
    assert user.theme == "system"


def test_create_profile_twice_raises(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))

    with pytest.raises(ProfileExistsError):
        profile_service.create_profile(db_session, ProfileCreate(name="Someone Else"))


def test_update_profile_changes_name_and_theme(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))

    updated = profile_service.update_profile(
        db_session, ProfileUpdate(name="Aryan M", theme="dark")
    )

    assert updated.name == "Aryan M"
    assert updated.theme == "dark"


def test_update_profile_leaves_omitted_fields_untouched(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))

    updated = profile_service.update_profile(db_session, ProfileUpdate(theme="light"))

    assert updated.name == "Aryan"
    assert updated.theme == "light"


def test_update_profile_without_onboarding_raises(db_session):
    with pytest.raises(ProfileNotFoundError):
        profile_service.update_profile(db_session, ProfileUpdate(name="Ghost"))


from schemas.profile import TrackCreate
from services.profile_service import TrackNotFoundError


def _onboard(db_session):
    return profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))


def test_create_track_is_active_by_default(db_session):
    _onboard(db_session)

    track = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    assert track.is_active is True
    assert profile_service.get_active_track(db_session).id == track.id


def test_creating_a_second_track_deactivates_the_first(db_session):
    _onboard(db_session)
    first = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    second = profile_service.create_track(
        db_session, TrackCreate(topic="React", experience_level="intermediate")
    )

    db_session.refresh(first)
    assert first.is_active is False
    assert second.is_active is True
    active = [t for t in profile_service.list_tracks(db_session) if t.is_active]
    assert len(active) == 1


def test_list_tracks_orders_most_recent_first(db_session):
    _onboard(db_session)
    first = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )
    second = profile_service.create_track(
        db_session, TrackCreate(topic="React", experience_level="intermediate")
    )

    # id is the tiebreak because both tracks can land in the same
    # func.now() second in a fast test run — created_at alone isn't
    # reliably ordered in that case.
    listed = profile_service.list_tracks(db_session)

    assert [t.id for t in listed] == [second.id, first.id]


def test_activate_track_switches_the_active_one(db_session):
    _onboard(db_session)
    first = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )
    profile_service.create_track(
        db_session, TrackCreate(topic="React", experience_level="intermediate")
    )

    reactivated = profile_service.activate_track(db_session, first.id)

    assert reactivated.is_active is True
    active = [t for t in profile_service.list_tracks(db_session) if t.is_active]
    assert len(active) == 1
    assert active[0].id == first.id


def test_activate_unknown_track_raises(db_session):
    _onboard(db_session)

    with pytest.raises(TrackNotFoundError):
        profile_service.activate_track(db_session, 4242)


def test_create_track_without_profile_raises(db_session):
    with pytest.raises(ProfileNotFoundError):
        profile_service.create_track(
            db_session, TrackCreate(topic="Python", experience_level="beginner")
        )


def test_get_active_track_returns_none_when_no_tracks(db_session):
    _onboard(db_session)

    assert profile_service.get_active_track(db_session) is None


def test_get_track_returns_the_track(db_session):
    _onboard(db_session)
    created = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    fetched = profile_service.get_track(db_session, created.id)

    assert fetched.id == created.id


def test_get_track_unknown_raises(db_session):
    _onboard(db_session)

    with pytest.raises(TrackNotFoundError):
        profile_service.get_track(db_session, 4242)


from models.assessment import Assessment, AssessmentQuestion
from models.interview import Interview, InterviewQuestion, ProctoringEvent


def test_delete_profile_cascades_to_every_table(db_session):
    user = _onboard(db_session)
    track = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()
    db_session.add(
        AssessmentQuestion(
            assessment_id=assessment.id,
            order_index=0,
            type="mcq",
            topic_tag="loops",
            question="What does `range(3)` produce?",
            options=["0,1,2", "1,2,3", "0,1,2,3", "1,2"],
            correct_option=0,
        )
    )

    interview = Interview(
        track_id=track.id, level="intermediate", question_count=5, status="active"
    )
    db_session.add(interview)
    db_session.commit()
    db_session.add(
        InterviewQuestion(
            interview_id=interview.id,
            order_index=0,
            question="Explain the GIL.",
            expected_points=["single lock"],
        )
    )
    db_session.add(
        ProctoringEvent(
            interview_id=interview.id,
            type="looking_away",
            severity="warning",
            detail="yaw 30deg",
            warning_index=1,
        )
    )
    db_session.commit()

    # Captured as plain ints before deleting — after delete_profile,
    # touching .id on these ORM objects would itself trigger a refresh
    # (SQLAlchemy expires every tracked object's attributes on every
    # commit by default) against rows that the database has already
    # removed via cascade, raising rather than returning None.
    user_id, track_id, assessment_id, interview_id = (
        user.id,
        track.id,
        assessment.id,
        interview.id,
    )

    profile_service.delete_profile(db_session)

    # assessment/interview were removed by the database's own FK cascade,
    # not by SQLAlchemy's ORM-level cascade (LearningTrack has no declared
    # `relationship()` to either), so the session doesn't know to drop them
    # from its identity map on its own. expunge_all() clears it, so the
    # `.get()` calls below issue genuinely fresh queries instead of trying
    # to reconcile stale in-memory objects against rows that are gone.
    db_session.expunge_all()

    assert db_session.get(User, user_id) is None
    assert db_session.get(LearningTrack, track_id) is None
    assert db_session.get(Assessment, assessment_id) is None
    assert db_session.query(AssessmentQuestion).count() == 0
    assert db_session.get(Interview, interview_id) is None
    assert db_session.query(InterviewQuestion).count() == 0
    assert db_session.query(ProctoringEvent).count() == 0


def test_delete_profile_when_none_exists_is_a_noop(db_session):
    profile_service.delete_profile(db_session)  # must not raise

    assert profile_service.get_profile(db_session) is None
