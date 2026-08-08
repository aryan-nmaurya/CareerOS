from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InterviewLevel = Literal["beginner", "intermediate", "advanced"]
InterviewStatus = Literal["setup", "active", "completed", "terminated"]


class InterviewQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    question: str
    expected_points: list[str]
    transcript: str | None
    answer_duration_s: int | None


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
    questions: list[InterviewQuestionOut]


class StartInterview(BaseModel):
    level: InterviewLevel
    question_count: Literal[5, 8, 10]


class AnswerSave(BaseModel):
    transcript: str
    duration_s: int = Field(ge=0)
