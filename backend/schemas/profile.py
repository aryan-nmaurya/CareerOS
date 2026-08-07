from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
Theme = Literal["light", "dark", "system"]


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    theme: Theme | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    theme: Theme
    created_at: datetime


class TrackCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    experience_level: ExperienceLevel


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic: str
    experience_level: ExperienceLevel
    is_active: bool
    created_at: datetime
