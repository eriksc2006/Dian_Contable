from __future__ import annotations

from decimal import Decimal

from core.config import CONFIDENCE_WEIGHTS, settings
from core.models import (
    AccountType,
    ClassificationResult,
    InvoiceRecord,
    InvoiceStatus,
    NaturalezaCuenta,
    TipoReporte,
)
from utils.numbers import values_match
from utils.strings import normalize_text, similarity_token


def score_matches(flags: dict[str, bool]) -> float:
    total = 0.0
    for key, weight in CONFIDENCE_WEIGHTS.items():
        if flags.get(key):
            total += weight
    return round(total, 4)


def decide_status(confidence: float, critical: bool, threshold: float | None = None) -> InvoiceStatus:
    limit = settings.confidence_threshold if threshold is None else threshold
    if confidence >= limit and not critical:
        return InvoiceStatus.AUTOMATICO
    return InvoiceStatus.REQUIERE_REVISION


def detect_critical(
    invoice: InvoiceRecord,
    duplicates: set[str],
    classified_account: str = "",
    value_ok: bool = True,
    date_ok: bool = True,
    found_in_software: bool | None = None,
) -> list[str]:
    alerts: list[str] = []
    if not invoice.nit:
        alerts.append("⚠️ Ausencia de NIT")
    if not invoice.numero_factura:
        alerts.append("⚠️ Ausencia de Número de Factura")
    key = f"{invoice.nit}|{invoice.numero_factura}"
    if key in duplicates:
        alerts.append("⚠️ Factura duplicada")
    if not value_ok or invoice.valor_total < 0:
        alerts.append("⚠️ Inconsistencia en valores")
    if invoice.valor_base + invoice.valor_iva - invoice.valor_total not in (
        Decimal("0.00"),
        Decimal("-0.00"),
    ) and abs(invoice.valor_base + invoice.valor_iva - invoice.valor_total) > Decimal("1.00"):
        alerts.append("⚠️ Datos inconsistentes: base + IVA no cuadra con el total")
    if not date_ok:
        alerts.append("⚠️ Inconsistencia en fechas")
    if not classified_account:
        alerts.append("⚠️ Cuenta no asignada")
    if found_in_software is False:
        alerts.append("⚠️ Factura no encontrada en el software contable")
    return alerts


def field_flags_for_classification(
    invoice: InvoiceRecord,
    account: AccountType | None,
) -> dict[str, bool]:
    flags = {
        "nit": bool(invoice.nit),
        "factura": bool(invoice.numero_factura),
        "fecha": bool(invoice.fecha),
        "valor": invoice.valor_total > 0,
        "cuenta": bool(account and account.codigo),
        "descripcion": False,
    }
    if account:
        flags["descripcion"] = bool(
            similarity_token(
                invoice.concepto or invoice.razon_social,
                f"{account.nombre} {account.palabras_clave}",
            )
            >= 0.2
            or (
                normalize_text(account.palabras_clave)
                and any(
                    token in normalize_text(invoice.concepto + " " + invoice.razon_social)
                    for token in normalize_text(account.palabras_clave).split()
                )
            )
        )
    return flags


def field_flags_for_software(
    invoice: InvoiceRecord,
    software: dict,
    account_code: str = "",
) -> dict[str, bool]:
    nit_sw = str(software.get("nit") or software.get("NIT") or "")
    doc_sw = str(
        software.get("documento")
        or software.get("Documento")
        or software.get("numero_factura")
        or ""
    )
    fecha_sw = software.get("fecha") or software.get("Fecha(mm/dd/yyyy)") or software.get("Fecha")
    valor_sw = software.get("valor") or software.get("Valor") or software.get("valor_total")
    cuenta_sw = str(software.get("cuenta") or software.get("Cuenta") or "")
    det_sw = str(software.get("detalle") or software.get("Detalle") or "")

    flags = {
        "nit": bool(invoice.nit) and invoice.nit in digits_safe(nit_sw),
        "factura": bool(invoice.numero_factura)
        and normalize_text(invoice.numero_factura) in normalize_text(doc_sw),
        "fecha": False,
        "valor": False,
        "cuenta": bool(account_code) and (not cuenta_sw or account_code in cuenta_sw),
        "descripcion": similarity_token(invoice.razon_social, det_sw) >= 0.4,
    }
    if fecha_sw:
        try:
            from utils.dates import parse_date

            flags["fecha"] = parse_date(fecha_sw) == invoice.fecha
        except Exception:
            flags["fecha"] = False
    if valor_sw not in (None, ""):
        flags["valor"] = values_match(valor_sw, invoice.valor_total) or values_match(
            valor_sw, invoice.valor_base
        )
    return flags


def digits_safe(value: str) -> str:
    from utils.strings import digits_only

    return digits_only(value)
