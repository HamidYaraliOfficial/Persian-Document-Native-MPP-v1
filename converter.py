from __future__ import annotations

from pathlib import Path
from .models import ProjectSpec
from .parsers import parse_file
from .mpp_writer import MPPWriter, MPPUnavailable
from .mspdi_writer import write_mspdi


class ConversionResult:
    def __init__(self, project: ProjectSpec, output: Path, native_mpp: bool):
        self.project = project
        self.output = output
        self.native_mpp = native_mpp


def convert_to_mpp(
    input_file: str | Path,
    output_file: str | Path | None = None,
    *,
    project_name: str | None = None,
    visible_project: bool = False,
    allow_mspdi_fallback: bool = False,
) -> ConversionResult:
    source = Path(input_file)
    project = parse_file(source, project_name=project_name)
    target = Path(output_file) if output_file else source.with_suffix(".mpp")
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        actual = MPPWriter(visible=visible_project).write(project, target)
        return ConversionResult(project, actual, native_mpp=True)
    except MPPUnavailable:
        if not allow_mspdi_fallback:
            raise
        actual = write_mspdi(project, target.with_suffix(".xml"))
        return ConversionResult(project, actual, native_mpp=False)
