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
