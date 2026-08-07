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
