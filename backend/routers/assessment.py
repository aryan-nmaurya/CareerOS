from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai.client import AIClient, get_ai_client
from db.session import get_db
from schemas.assessment import AnswerSave, AssessmentOut
from services import assessment_service
from services.assessment_service import (
    AssessmentAlreadySubmittedError,
    AssessmentNotApplicableError,
    AssessmentNotFoundError,
    QuestionNotFoundError,
)
from services.profile_service import TrackNotFoundError

router = APIRouter(tags=["assessment"])

_TRACK_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "track_not_found", "message": "That learning track does not exist."},
)
_ASSESSMENT_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "assessment_not_found", "message": "That assessment does not exist."},
)
_QUESTION_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "question_not_found", "message": "That question does not exist."},
)
_ALREADY_SUBMITTED = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={
        "code": "assessment_already_submitted",
        "message": "This assessment has already been submitted.",
    },
)
_NOT_APPLICABLE = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={
        "code": "assessment_not_applicable",
        "message": "Beginner tracks skip assessment and go straight to the roadmap.",
    },
)


@router.post(
    "/api/tracks/{track_id}/assessment",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
)
def start_assessment(
    track_id: int,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    try:
        assessment = assessment_service.start_assessment(db, ai_client, track_id)
        return assessment_service.to_assessment_out(assessment)
    except TrackNotFoundError:
        raise _TRACK_MISSING
    except AssessmentNotApplicableError:
        raise _NOT_APPLICABLE


@router.get("/api/assessments", response_model=list[AssessmentOut])
def list_assessments(db: Session = Depends(get_db)):
    return [
        assessment_service.to_assessment_out(a)
        for a in assessment_service.list_assessments(db)
    ]


@router.get("/api/assessments/{assessment_id}", response_model=AssessmentOut)
def read_assessment(assessment_id: int, db: Session = Depends(get_db)):
    try:
        assessment = assessment_service.get_assessment(db, assessment_id)
        return assessment_service.to_assessment_out(assessment)
    except AssessmentNotFoundError:
        raise _ASSESSMENT_MISSING


@router.patch("/api/assessments/{assessment_id}/answers", status_code=status.HTTP_204_NO_CONTENT)
def save_answer(assessment_id: int, payload: AnswerSave, db: Session = Depends(get_db)):
    try:
        assessment_service.save_answer(db, assessment_id, payload)
    except AssessmentNotFoundError:
        raise _ASSESSMENT_MISSING
    except QuestionNotFoundError:
        raise _QUESTION_MISSING
    except AssessmentAlreadySubmittedError:
        raise _ALREADY_SUBMITTED


@router.post("/api/assessments/{assessment_id}/submit", response_model=AssessmentOut)
def submit_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    try:
        assessment = assessment_service.submit_assessment(db, ai_client, assessment_id)
        return assessment_service.to_assessment_out(assessment)
    except AssessmentNotFoundError:
        raise _ASSESSMENT_MISSING
    except AssessmentAlreadySubmittedError:
        raise _ALREADY_SUBMITTED
