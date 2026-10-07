from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Dependency:
    predecessor: int
    link: str = "FS"
    lag_days: float = 0.0


@dataclass
class TaskSpec:
    name: str
    level: int = 1
    duration_days: Optional[float] = None
    start: Optional[date] = None
    finish: Optional[date] = None
    predecessors: list[Dependency] = field(default_factory=list)
    resource_names: list[str] = field(default_factory=list)
    notes: str = ""
    milestone: bool = False
    source_line: Optional[int] = None
    source_table: Optional[int] = None

    @property
    def is_summary(self) -> bool:
        return False  # determined during planning from the hierarchy


@dataclass
class ProjectSpec:
    name: str
    start: Optional[date] = None
    tasks: list[TaskSpec] = field(default_factory=list)
    default_duration_days: float = 1.0
    calendar_name: str = "Standard"
    metadata: dict[str, str] = field(default_factory=dict)
