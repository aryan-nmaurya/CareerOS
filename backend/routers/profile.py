from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.profile import ProfileCreate, ProfileOut, ProfileUpdate
from services import profile_service
from services.profile_service import ProfileExistsError, ProfileNotFoundError

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut, responses={204: {"description": "Not onboarded"}})
def read_profile(db: Session = Depends(get_db)):
    user = profile_service.get_profile(db)
    if user is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return user


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    try:
        return profile_service.create_profile(db, payload)
    except ProfileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "profile_exists", "message": "A profile already exists."},
        )


@router.patch("", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    try:
        return profile_service.update_profile(db, payload)
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "profile_not_found", "message": "No profile yet."},
        )
