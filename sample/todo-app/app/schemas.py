from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Annotated[int, Field(ge=1, le=3)]


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    done: bool
    due_on: date | None
    priority: Priority
    tags: list[TagOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_on: date | None = None
    priority: Priority = 2
    tags: list[str] = Field(default_factory=list)


class TodoPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_on: date | None = None
    priority: Priority | None = None
    done: bool | None = None
    tags: list[str] | None = None


class TodoListQuery(BaseModel):
    filter: Literal["all", "open", "done"] = "all"
    q: str | None = None
