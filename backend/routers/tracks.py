from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.profile import TrackCreate, TrackOut
from services import profile_service
from services.profile_service import ProfileNotFoundError, TrackNotFoundError

router = APIRouter(prefix="/api/tracks", tags=["tracks"])

_PROFILE_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "profile_not_found", "message": "No profile yet."},
)
_TRACK_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "track_not_found", "message": "That learning track does not exist."},
)


@router.get("", response_model=list[TrackOut])
def list_tracks(db: Session = Depends(get_db)):
    return profile_service.list_tracks(db)


@router.post("", response_model=TrackOut, status_code=status.HTTP_201_CREATED)
def create_track(payload: TrackCreate, db: Session = Depends(get_db)):
    try:
        return profile_service.create_track(db, payload)
    except ProfileNotFoundError:
        raise _PROFILE_MISSING


@router.post("/{track_id}/activate", response_model=TrackOut)
def activate_track(track_id: int, db: Session = Depends(get_db)):
    try:
        return profile_service.activate_track(db, track_id)
    except TrackNotFoundError:
        raise _TRACK_MISSING
