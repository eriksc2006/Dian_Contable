from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from core.exceptions import ValidationErrorApp


_DATE_FORMATS = (
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%m-%d-%Y",
)


def parse_date(value: Any) -> date:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValidationErrorApp("Fecha vacía")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()

    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        raise ValidationErrorApp("Fecha vacía")

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue

    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        raise ValidationErrorApp(f"Fecha no reconocida: {value}")
    return parsed.date()


def format_date_mmddyyyy(value: date | datetime) -> str:
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%m/%d/%Y")
