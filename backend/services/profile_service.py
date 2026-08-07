from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import LearningTrack, User
from schemas.profile import ProfileCreate, ProfileUpdate, TrackCreate


class ProfileExistsError(Exception):
    """A profile already exists; CareerOS is single-user."""


class ProfileNotFoundError(Exception):
    """An operation needed a profile but onboarding has not happened yet."""


class TrackNotFoundError(Exception):
    """The requested learning track does not exist."""


def get_profile(db: Session) -> User | None:
    return db.scalars(select(User).order_by(User.id)).first()


def create_profile(db: Session, payload: ProfileCreate) -> User:
    if get_profile(db) is not None:
        raise ProfileExistsError

    user = User(name=payload.name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_profile(db: Session, payload: ProfileUpdate) -> User:
    user = get_profile(db)
    if user is None:
        raise ProfileNotFoundError

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.theme is not None:
        user.theme = payload.theme

    db.commit()
    db.refresh(user)
    return user


def list_tracks(db: Session) -> list[LearningTrack]:
    return list(
        db.scalars(select(LearningTrack).order_by(LearningTrack.created_at.desc()))
    )


def get_active_track(db: Session) -> LearningTrack | None:
    return db.scalars(
        select(LearningTrack).where(LearningTrack.is_active.is_(True))
    ).first()


def create_track(db: Session, payload: TrackCreate) -> LearningTrack:
    """Creating a track makes it the active one. Exactly one track is active at
    any time — the dashboard and roadmap always render that track."""
    user = get_profile(db)
    if user is None:
        raise ProfileNotFoundError

    for existing in list_tracks(db):
        existing.is_active = False

    track = LearningTrack(
        user_id=user.id,
        topic=payload.topic.strip(),
        experience_level=payload.experience_level,
        is_active=True,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def activate_track(db: Session, track_id: int) -> LearningTrack:
    target = db.get(LearningTrack, track_id)
    if target is None:
        raise TrackNotFoundError

    for existing in list_tracks(db):
        existing.is_active = existing.id == track_id

    db.commit()
    db.refresh(target)
    return target


def get_track(db: Session, track_id: int) -> LearningTrack:
    track = db.get(LearningTrack, track_id)
    if track is None:
        raise TrackNotFoundError
    return track
