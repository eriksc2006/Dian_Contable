from __future__ import annotations

import pandas as pd

from core.exceptions import ValidationErrorApp
from core.models import (
    ClassificationResult,
    InvoiceRecord,
    InvoiceStatus,
    MatchResult,
    invoice_key,
)
from services.confidence_service import (
    decide_status,
    detect_critical,
    field_flags_for_software,
    score_matches,
)
from services.excel_service import pick_column
from utils.numbers import parse_decimal
from utils.strings import digits_only, normalize_text


def index_software_rows(df) -> list[dict]:
    nit_col = pick_column(df, ["nit", "NIT"])
    doc_col = pick_column(df, ["documento", "Documento", "numero", "factura", "Documento Ref."])
    rows = []
    for _, row in df.iterrows():
        item = {str(k): ("" if v is None else v) for k, v in row.items()}
        if nit_col:
            item["nit"] = digits_only(row.get(nit_col, ""))
        if doc_col:
            item["documento"] = str(row.get(doc_col, "")).strip()
        rows.append(item)
    return rows


def software_base_value(row: dict) -> object | None:
    for column, value in row.items():
        if normalize_text(column) == "BASE":
            return value
    return None


def software_base_is_zero(row: dict) -> bool:
    value = software_base_value(row)
    if value is None or pd.isna(value) or not str(value).strip():
        return False
    try:
        return parse_decimal(value) == 0
    except ValidationErrorApp:
        return False


def match_invoices(
    invoices: list[InvoiceRecord],
    classifications: dict[str, ClassificationResult],
    software_rows: list[dict],
) -> list[MatchResult]:
    results: list[MatchResult] = []

    for invoice in invoices:
        classification = classifications.get(invoice.id)
        account = classification.cuenta_principal if classification else ""
        invoice_key_value = invoice_key(invoice.nit, invoice.numero_factura)
        invoice_number = normalize_text(invoice.numero_factura)
        exact_rows = (
            [
                row
                for row in software_rows
                if invoice_key(row.get("nit", ""), row.get("documento", "")) == invoice_key_value
            ]
            if invoice_number
            else []
        )
        number_rows = (
            [
                row
                for row in software_rows
                if normalize_text(row.get("documento", "")) == invoice_number
            ]
            if invoice_number
            else []
        )
        matching_rows = exact_rows or number_rows
        zero_base_rows = [row for row in matching_rows if software_base_is_zero(row)]
        candidate_rows = zero_base_rows or matching_rows or software_rows
        best_row = None
        best_score = -1.0
        best_flags: dict[str, bool] = {}

        for row in candidate_rows:
            flags = field_flags_for_software(invoice, row, account)
            score = score_matches(flags)
            if score > best_score:
                best_score = score
                best_flags = flags
                best_row = row

        encontrada = False
        if best_row is not None:
            has_invoice_match = bool(matching_rows) or (
                best_flags.get("nit") and best_flags.get("factura") and best_score >= 0.50
            )
            encontrada = has_invoice_match and software_base_is_zero(best_row)

        alerts = detect_critical(
            invoice,
            duplicates=set(),
            classified_account=account,
            value_ok=best_flags.get("valor", True) if encontrada else True,
            date_ok=best_flags.get("fecha", True) if encontrada else True,
            found_in_software=encontrada,
        )
        if encontrada and not best_flags.get("valor", True):
            alerts.append("⚠️ Valor no coincide")
        critical = (not encontrada) or bool(alerts)
        status = (
            InvoiceStatus.ENCONTRADA
            if encontrada and decide_status(best_score if best_score >= 0 else 0, critical) == InvoiceStatus.AUTOMATICO
            else InvoiceStatus.NO_ENCONTRADA
            if not encontrada
            else decide_status(max(best_score, 0), critical)
        )
        if encontrada and not critical:
            status = InvoiceStatus.ENCONTRADA
        elif not encontrada:
            status = InvoiceStatus.NO_ENCONTRADA
            if InvoiceStatus.REQUIERE_REVISION not in (status,):
                status = InvoiceStatus.NO_ENCONTRADA

        results.append(
            MatchResult(
                invoice_id=invoice.id,
                encontrada=encontrada,
                confidence=max(best_score, 0.0),
                status=status if encontrada else InvoiceStatus.NO_ENCONTRADA,
                alerts=alerts,
                software_row=best_row or {},
            )
        )
    return results
