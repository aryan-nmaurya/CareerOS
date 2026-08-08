from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai.client import AIClient, get_ai_client
from db.session import get_db
from schemas.interview import AnswerSave, InterviewOut, StartInterview
from services import interview_service
from services.interview_service import (
    InterviewNotActiveError,
    InterviewNotFoundError,
    QuestionNotFoundError,
)
from services.profile_service import TrackNotFoundError

router = APIRouter(tags=["interview"])

_TRACK_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "track_not_found", "message": "That learning track does not exist."},
)
_INTERVIEW_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "interview_not_found", "message": "That interview does not exist."},
)
_QUESTION_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "question_not_found", "message": "That question does not exist."},
)
_NOT_ACTIVE = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={"code": "interview_not_active", "message": "This interview is no longer active."},
)


@router.post(
    "/api/tracks/{track_id}/interviews",
    response_model=InterviewOut,
    status_code=status.HTTP_201_CREATED,
)
def start_interview(
    track_id: int,
    payload: StartInterview,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    try:
        interview = interview_service.start_interview(
            db, ai_client, track_id, payload.level, payload.question_count
        )
        return interview_service.to_interview_out(interview)
    except TrackNotFoundError:
        raise _TRACK_MISSING


@router.get("/api/interviews/{interview_id}", response_model=InterviewOut)
def read_interview(interview_id: int, db: Session = Depends(get_db)):
    try:
        interview = interview_service.get_interview(db, interview_id)
        return interview_service.to_interview_out(interview)
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING


@router.post(
    "/api/interviews/{interview_id}/questions/{question_id}/answer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def save_answer(
    interview_id: int,
    question_id: int,
    payload: AnswerSave,
    db: Session = Depends(get_db),
):
    try:
        interview_service.record_answer(
            db, interview_id, question_id, payload.transcript, payload.duration_s
        )
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING
    except QuestionNotFoundError:
        raise _QUESTION_MISSING


@router.post("/api/interviews/{interview_id}/submit", response_model=InterviewOut)
def submit_interview(interview_id: int, db: Session = Depends(get_db)):
    try:
        interview = interview_service.complete_interview(db, interview_id)
        return interview_service.to_interview_out(interview)
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING
    except InterviewNotActiveError:
        raise _NOT_ACTIVE


@router.post("/api/interviews/{interview_id}/quit", response_model=InterviewOut)
def quit_interview(interview_id: int, db: Session = Depends(get_db)):
    try:
        interview = interview_service.quit_interview(db, interview_id)
        return interview_service.to_interview_out(interview)
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING
    except InterviewNotActiveError:
        raise _NOT_ACTIVE
