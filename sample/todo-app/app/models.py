from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Tag:
    id: int
    name: str


@dataclass
class Todo:
    id: int
    title: str
    done: bool
    due_on: date | None
    priority: int
    created_at: datetime
    updated_at: datetime
    tags: list[Tag] = field(default_factory=list)
