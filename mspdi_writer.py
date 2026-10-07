from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

from .models import ProjectSpec
from .planner import normalize_project, _is_summary

NS = "http://schemas.microsoft.com/project"

try:
    import xml.etree.ElementTree as ET
    ET.register_namespace("", NS)
except Exception:
    pass

def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _iso(d):
    return datetime(d.year, d.month, d.day, 8, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if d else None


def write_mspdi(project: ProjectSpec, output_path: str | Path) -> Path:
    """Write Microsoft Project XML (MSPDI), not MPP. Project can open/save it as MPP."""
    project = normalize_project(project)
    path = Path(output_path).with_suffix(".xml")
    root = Element(q("Project"))
    SubElement(root, q("SaveVersion")).text = "14"
    SubElement(root, q("Name")).text = project.name
    SubElement(root, q("Title")).text = project.name
    SubElement(root, q("ScheduleFromStart")).text = "1"
    if project.start:
        SubElement(root, q("StartDate")).text = _iso(project.start)
        SubElement(root, q("CurrentDate")).text = _iso(project.start)

    # Standard calendar, Monday-Friday, 08:00-17:00 with 1h lunch.
    cals = SubElement(root, q("Calendars"))
    cal = SubElement(cals, q("Calendar"))
    SubElement(cal, q("UID")).text = "1"
    SubElement(cal, q("Name")).text = "Standard"
    SubElement(cal, q("IsBaseCalendar")).text = "1"

    tasks_el = SubElement(root, q("Tasks"))
    counters: list[int] = []
    for idx, task in enumerate(project.tasks, start=1):
        level = max(1, int(task.level))
        while len(counters) < level:
            counters.append(0)
        counters = counters[:level]
        counters[-1] += 1
        for pos in range(level, len(counters)):
            counters[pos] = 0
        outline_number = ".".join(str(x) for x in counters if x)

        te = SubElement(tasks_el, q("Task"))
        SubElement(te, q("UID")).text = str(idx)
        SubElement(te, q("ID")).text = str(idx)
        SubElement(te, q("Name")).text = task.name
        SubElement(te, q("OutlineLevel")).text = str(level)
        SubElement(te, q("OutlineNumber")).text = outline_number
        is_summary = _is_summary(project.tasks, idx - 1)
        SubElement(te, q("Summary")).text = "1" if is_summary else "0"
        SubElement(te, q("Milestone")).text = "1" if task.milestone else "0"
        if task.duration_days is not None and not is_summary:
            mins = int(round(task.duration_days * 8 * 60))
            SubElement(te, q("Duration")).text = f"PT{mins}M"
            SubElement(te, q("DurationFormat")).text = "7"
        if task.start:
            SubElement(te, q("Start")).text = _iso(task.start)
        if task.finish:
            SubElement(te, q("Finish")).text = _iso(task.finish)
        if task.notes:
            SubElement(te, q("Notes")).text = task.notes
        for dep in task.predecessors:
            if 1 <= dep.predecessor <= len(project.tasks):
                re = SubElement(te, q("PredecessorLink"))
                SubElement(re, q("PredecessorUID")).text = str(dep.predecessor)
                link_map = {"FS": "1", "SS": "2", "FF": "3", "SF": "4"}
                SubElement(re, q("Type")).text = link_map.get(dep.link.upper(), "1")
                SubElement(re, q("LinkLag")).text = str(int(round(dep.lag_days * 480)))
                SubElement(re, q("LagFormat")).text = "7"

    ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path
