from __future__ import annotations

import argparse
import json
from pathlib import Path

from .converter import convert_to_mpp


def main():
    parser = argparse.ArgumentParser(description="تبدیل سند فارسی PDF/DOCX به Microsoft Project MPP")
    parser.add_argument("input", help="مسیر فایل PDF یا DOCX")
    parser.add_argument("-o", "--output", help="مسیر فایل خروجی .mpp")
    parser.add_argument("--name", help="نام پروژه")
    parser.add_argument("--visible-project", action="store_true", help="Microsoft Project را در زمان تبدیل قابل مشاهده کن")
    parser.add_argument("--fallback-xml", action="store_true", help="در صورت نبود Microsoft Project، MSPDI XML تولید کن")
    args = parser.parse_args()

    result = convert_to_mpp(
        args.input, args.output, project_name=args.name,
        visible_project=args.visible_project,
        allow_mspdi_fallback=args.fallback_xml,
    )
    print(json.dumps({
        "output": str(Path(result.output).resolve()),
        "native_mpp": result.native_mpp,
        "project": result.project.name,
        "task_count": len(result.project.tasks),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
