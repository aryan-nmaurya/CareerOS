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
