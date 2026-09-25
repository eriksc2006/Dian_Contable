from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def digits_only(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def nit_without_dv(value: Any) -> str:
    digits = digits_only(value)
    if len(digits) > 9:
        return digits[:-1]
    return digits


def pad_comprobante(number: int, width: int = 5) -> str:
    return str(int(number)).zfill(width)


def similarity_token(a: Any, b: Any) -> float:
    left = set(normalize_text(a).split())
    right = set(normalize_text(b).split())
    if not left or not right:
        return 0.0
    inter = left & right
    union = left | right
    return len(inter) / len(union)


def slug(value: Any) -> str:
    return normalize_text(value).replace(" ", "_")
