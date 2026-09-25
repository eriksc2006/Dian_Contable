from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import pandas as pd

from core.exceptions import ValidationErrorApp

TWOPLACES = Decimal("0.01")


def parse_decimal(value: Any) -> Decimal:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", ""}:
        return Decimal("0.00")

    text = text.replace("$", "").replace(" ", "")
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    elif text.count(".") >= 1 and text.count(",") == 1:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") > 1:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(",", "").replace(".", "")
        try:
            return Decimal(text).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise ValidationErrorApp(f"Valor numérico inválido: {value}") from exc

    try:
        return Decimal(text).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValidationErrorApp(f"Valor numérico inválido: {value}") from exc


def format_decimal_co(value: Decimal | int | float | str) -> str:
    quantized = parse_decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    integer, fraction = f"{abs(quantized):.2f}".split(".")
    return f"{sign}{integer},{fraction}"


def values_match(a: Any, b: Any, tolerance: Decimal = Decimal("0.01")) -> bool:
    return abs(parse_decimal(a) - parse_decimal(b)) <= tolerance
