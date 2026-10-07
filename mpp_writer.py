from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

from .models import ProjectSpec
from .planner import normalize_project, _is_summary


class MPPUnavailable(RuntimeError):
    pass


class MPPWriter:
    """Create a native Microsoft Project .mpp through the installed desktop app.

    Native MPP generation is delegated to Microsoft Project because the MPP format is
    proprietary and MPXJ currently documents MPP writing as unsupported.
    """

    def __init__(self, visible: bool = False):
        self.visible = visible

    def _load_com(self):
        if __import__("platform").system() != "Windows":
            raise MPPUnavailable("تولید مستقیم MPP فقط روی Windows با Microsoft Project نصب‌شده فعال است.")
        try:
            import win32com.client  # type: ignore
        except ImportError as exc:
            raise MPPUnavailable("pywin32 نصب نیست. اجرا کنید: pip install pywin32") from exc
        try:
            app = win32com.client.DispatchEx("MSProject.Application")
            app.Visible = self.visible
            app.DisplayAlerts = False
            return app
        except Exception as exc:
            raise MPPUnavailable(
                "Microsoft Project از طریق COM در دسترس نیست. Microsoft Project Desktop را نصب و فعال کنید."
            ) from exc

    @staticmethod
    def _dt(d):
        return datetime.combine(d, time(8, 0, 0)) if d else None

    @staticmethod
    def _duration_text(days: float) -> str:
        if days <= 0:
            return "0d"
        # Project's standard calendar is assumed to have 8 working hours/day.
        hours = round(days * 8, 4)
        if abs(hours - round(hours)) < 1e-9:
            return f"{int(round(hours))}h"
        return f"{hours:g}h"

    @staticmethod
    def _pred_text(preds):
        chunks = []
        for p in preds:
            lag = ""
            if p.lag_days:
                sign = "+" if p.lag_days >= 0 else "-"
                lag = f"{sign}{abs(p.lag_days):g}d"
            chunks.append(f"{p.predecessor}{p.link}{lag}")
        return ",".join(chunks)

    def write(self, project: ProjectSpec, output_path: str | Path) -> Path:
        project = normalize_project(project)
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix.lower() != ".mpp":
            output = output.with_suffix(".mpp")

        app = self._load_com()
        active = None
        try:
            app.FileNew()
            active = app.ActiveProject
            if project.name:
                try:
                    active.Name = project.name
                except Exception:
                    pass
            if project.start:
                try:
                    active.ProjectStart = self._dt(project.start)
                except Exception:
                    pass

            # Add resources first so task assignments can reference resource IDs.
            resource_ids: dict[str, int] = {}
            for task in project.tasks:
                for resource in task.resource_names:
                    if resource not in resource_ids:
                        r = active.Resources.Add(resource)
                        resource_ids[resource] = int(r.ID)

            com_tasks = []
            for task in project.tasks:
                ct = active.Tasks.Add(task.name)
                com_tasks.append(ct)
                if task.duration_days is not None and not _is_summary(project.tasks, len(com_tasks) - 1):
                    if task.milestone or task.duration_days == 0:
                        ct.Milestone = True
                        ct.Duration = "0d"
                    else:
                        ct.Duration = self._duration_text(float(task.duration_days))
                if task.start:
                    ct.Start = self._dt(task.start)
                if task.finish and not task.start:
                    ct.Finish = self._dt(task.finish)
                if task.notes:
                    ct.Notes = task.notes
                # Preserve source information for traceability.
                if task.source_line is not None:
                    try:
                        ct.Text1 = f"Source line: {task.source_line}"
                    except Exception:
                        pass
                if task.source_table is not None:
                    try:
                        ct.Text2 = f"Source table: {task.source_table}"
                    except Exception:
                        pass

                # Set the requested WBS level. OutlineLevel is a read/write Project property.
                target = max(1, int(task.level))
                try:
                    current = int(ct.OutlineLevel)
                    while current < target:
                        ct.OutlineIndent()
                        current += 1
                    while current > target:
                        ct.OutlineOutdent()
                        current -= 1
                except Exception:
                    pass

                for resource in task.resource_names:
                    try:
                        ct.Assignments.Add(ResourceID=resource_ids[resource])
                    except Exception:
                        # Resource assignment should never block MPP generation.
                        pass

            # Apply dependencies only after every task exists.
            for idx, task in enumerate(project.tasks):
                if task.predecessors:
                    valid = [p for p in task.predecessors if 1 <= p.predecessor <= len(com_tasks)]
                    if valid:
                        try:
                            com_tasks[idx].Predecessors = self._pred_text(valid)
                        except Exception:
                            # Fall back to simple FS links where Project rejects localized syntax.
                            try:
                                com_tasks[idx].Predecessors = ",".join(str(p.predecessor) for p in valid)
                            except Exception:
                                pass

            # Force automatic scheduling for generated tasks where available.
            for ct in com_tasks:
                try:
                    ct.Manual = False
                except Exception:
                    pass

            # Saving through Project is what produces the native binary .mpp.
            active.SaveAs(str(output))
            if not output.exists():
                raise IOError(f"Microsoft Project گزارش موفقیت داد، اما فایل ایجاد نشد: {output}")
            return output
        finally:
            try:
                if active is not None:
                    active.Close(SaveChanges=True)
            except Exception:
                pass
            try:
                app.DisplayAlerts = True
            except Exception:
                pass
            try:
                app.Quit()
            except Exception:
                pass
