from __future__ import annotations

from datetime import date, timedelta
from .models import ProjectSpec, TaskSpec


def _is_summary(tasks: list[TaskSpec], index: int) -> bool:
    return index + 1 < len(tasks) and tasks[index + 1].level > tasks[index].level


def _working_days(start: date, days: float) -> date:
    if days <= 0:
        return start
    remaining = int(days + 0.999999)
    cur = start
    while remaining > 1:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            remaining -= 1
    return cur


def normalize_project(project: ProjectSpec) -> ProjectSpec:
    """Fill sensible defaults and keep hierarchy/dependency indices stable."""
    if not project.tasks:
        raise ValueError("هیچ فعالیت قابل تشخیصی از سند استخراج نشد.")
    start = project.start or date.today()
    project.start = start

    for task in project.tasks:
        if task.duration_days is None:
            task.duration_days = 0.0 if task.milestone else project.default_duration_days
        if task.start is None and task.finish is not None and task.duration_days > 0:
            # Approximate backwards using calendar days; Project will schedule using its calendar.
            task.start = task.finish - timedelta(days=max(0, int(task.duration_days) - 1))
        if task.start is None:
            task.start = start
        if task.finish is None and task.duration_days is not None:
            task.finish = _working_days(task.start, task.duration_days)
    return project
