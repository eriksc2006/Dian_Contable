from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from core.exceptions import MappingError
from core.logging_config import logger


def read_tabular(source: BytesIO | Path | str, filename: str | None = None) -> pd.DataFrame:
    name = filename or (str(source) if not isinstance(source, BytesIO) else "upload")
    suffix = Path(name).suffix.lower()
    logger.info("Leyendo archivo tabular: %s", name)

    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(source, engine="openpyxl" if suffix == ".xlsx" else None)
    elif suffix in {".csv", ".txt"}:
        raw = source.read() if hasattr(source, "read") else Path(source).read_bytes()
        if isinstance(source, BytesIO):
            source.seek(0)
        text = raw.decode("utf-8-sig", errors="replace")
        sep = ";" if text.count(";") >= text.count(",") else ","
        df = pd.read_csv(BytesIO(raw), sep=sep, dtype=str, encoding="utf-8-sig")
    else:
        raise MappingError(f"Extensión no soportada: {suffix or 'desconocida'}")

    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def pick_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    cols = {str(c).strip().lower(): c for c in df.columns}
    for alias in aliases:
        if alias.lower() in cols:
            return cols[alias.lower()]
    for alias in aliases:
        for original in df.columns:
            if alias.lower() in str(original).strip().lower():
                return original
    return None


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "datos") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()
