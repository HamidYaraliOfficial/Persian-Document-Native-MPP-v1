"""Small public facade for embedding the converter into another Python application."""

from .converter import convert_to_mpp, ConversionResult


def convert(input_path, output_path=None, project_name=None, **kwargs) -> ConversionResult:
    """Convert a Persian PDF/DOC/DOCX project document to native MPP on Windows."""
    return convert_to_mpp(
        input_path,
        output_path,
        project_name=project_name,
        **kwargs,
    )


__all__ = ["convert", "convert_to_mpp", "ConversionResult"]
