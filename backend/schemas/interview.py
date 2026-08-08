from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InterviewLevel = Literal["beginner", "intermediate", "advanced"]
InterviewStatus = Literal["setup", "active", "completed", "terminated"]
ProctoringEventType = Literal[
    "looking_away", "no_face", "multiple_faces", "excessive_noise", "background_voice"
]


class InterviewQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    question: str
    expected_points: list[str]
    transcript: str | None
    answer_duration_s: int | None
    technical_score: float | None
    communication_score: float | None
    confidence_score: float | None
    missing_concepts: list[str]
    better_answer: str | None
    feedback: str | None


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    level: InterviewLevel
    question_count: int
    status: InterviewStatus
    started_at: datetime
    ended_at: datetime | None
    termination_reason: str | None
    overall_score: float | None
    technical_score: float | None
    communication_score: float | None
    confidence_score: float | None
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    summary: str | None
    questions: list[InterviewQuestionOut]


class StartInterview(BaseModel):
    level: InterviewLevel
    question_count: Literal[5, 8, 10]


class AnswerSave(BaseModel):
    transcript: str
    duration_s: int = Field(ge=0)


class ProctoringEventIn(BaseModel):
    type: ProctoringEventType
    detail: str = ""


class ProctoringEventOut(BaseModel):
    warning_count: int
    should_terminate: bool
