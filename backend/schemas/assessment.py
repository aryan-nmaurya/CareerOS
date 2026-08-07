from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

QuestionType = Literal["mcq", "descriptive"]
AssessmentStatus = Literal["in_progress", "completed"]
EstimatedLevel = Literal["foundational", "intermediate", "advanced"]


class AssessmentQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    type: QuestionType
    topic_tag: str
    question: str
    options: list[str] | None = None
    correct_option: int | None = None
    expected_points: list[str] | None = None
    user_answer: str | None = None
    score: float | None = None
    ai_feedback: str | None = None


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    level: str
    status: AssessmentStatus
    started_at: datetime
    completed_at: datetime | None
    score: float | None
    estimated_level: EstimatedLevel | None
    strengths: list[str]
    weaknesses: list[str]
    summary: str | None
    questions: list[AssessmentQuestionOut]


class AnswerSave(BaseModel):
    question_id: int
    answer: str
