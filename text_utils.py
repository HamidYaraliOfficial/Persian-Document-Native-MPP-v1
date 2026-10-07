from __future__ import annotations

import re
from datetime import date
from typing import Optional

try:
    import jdatetime
except Exception:  # pragma: no cover
    jdatetime = None

ARABIC_TO_PERSIAN = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "ؤ": "و", "إ": "ا", "أ": "ا",
    "ـ": "",
})
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_text(text: str) -> str:
    text = (text or "").translate(ARABIC_TO_PERSIAN).translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in re.split(r"\r?\n+", text or "") if line.strip()]


def parse_number(text: str) -> Optional[float]:
    t = normalize_text(text).replace(",", "").replace("٬", "").replace("٫", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group(0)) if m else None


def parse_duration_days(text: str) -> Optional[float]:
    t = normalize_text(text).lower()
    if not t or t in {"-", "—", "- -"}:
        return None
    if any(x in t for x in ("milestone", "نقطه عطف", "مایلستون")):
        return 0.0
    n = parse_number(t)
    if n is None:
        return None
    if re.search(r"(hour|hours|hr|hrs|ساعت)", t):
        return n / 8.0
    if re.search(r"(week|weeks|wk|wks|هفته)", t):
        return n * 5.0
    if re.search(r"(month|months|ماه)", t):
        return n * 22.0
    return n


def parse_iso_or_local_date(text: str) -> Optional[date]:
    t = normalize_text(text).replace("-", "/").replace(".", "/")
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", t)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    # Jalali years in the typical Persian civil range.
    if 1200 <= y <= 1700:
        if not jdatetime:
            raise RuntimeError("برای تبدیل تاریخ شمسی، jdatetime نصب کنید: pip install jdatetime")
        try:
            return jdatetime.date(y, mo, d).togregorian()
        except Exception:
            return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def extract_field(text: str, patterns: list[str]) -> Optional[str]:
    t = normalize_text(text)
    for p in patterns:
        m = re.search(p, t, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_dependencies(text: str) -> list[tuple[int, str, float]]:
    t = normalize_text(text)
    if not t or t in {"-", "—"}:
        return []
    field = extract_field(t, [
        r"(?:predecessor|predecessors|depends\s*on|بعد از|پس از|وابسته به|پیش(?:‌|\s*)نیاز)\s*[:=]\s*(.+)$",
    ]) or t
    out: list[tuple[int, str, float]] = []
    for token in re.split(r"[,;،؛\s]+", field):
        if not token:
            continue
        m = re.fullmatch(r"(\d+)\s*(FS|SS|FF|SF)?(?:\s*([+-])\s*(\d+(?:\.\d+)?)\s*d(?:ays?)?)?", token, re.I)
        if not m:
            m = re.fullmatch(r"(\d+)(?:\s*(FS|SS|FF|SF))?(?:\s*([+-])\s*(\d+(?:\.\d+)?)\s*(روز|day|days))?", token, re.I)
        if m:
            pred = int(m.group(1))
            link = (m.group(2) or "FS").upper()
            amount = float(m.group(4) or 0)
            sign = -1 if m.group(3) == "-" else 1
            out.append((pred, link, sign * amount))
    return out
