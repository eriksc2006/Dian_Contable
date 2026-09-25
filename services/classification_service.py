from __future__ import annotations

from collections import Counter

import pandas as pd

from core.config import settings
from core.exceptions import MappingError
from core.logging_config import logger
from core.models import (
    AccountType,
    ClassificationResult,
    InvoiceRecord,
    InvoiceStatus,
    NaturalezaCuenta,
    TipoReporte,
)
from services.confidence_service import (
    decide_status,
    detect_critical,
    field_flags_for_classification,
    score_matches,
)
from services.excel_service import pick_column
from utils.strings import normalize_text, similarity_token


NATURALEZA_ALIASES = {
    "VENTA": NaturalezaCuenta.VENTA,
    "VENTAS": NaturalezaCuenta.VENTA,
    "INGRESO": NaturalezaCuenta.VENTA,
    "INGRESOS": NaturalezaCuenta.VENTA,
    "COMPRA": NaturalezaCuenta.COMPRA,
    "COMPRAS": NaturalezaCuenta.COMPRA,
    "GASTO": NaturalezaCuenta.COMPRA,
    "GASTOS": NaturalezaCuenta.COMPRA,
    "COSTO": NaturalezaCuenta.COSTOS,
    "COSTOS": NaturalezaCuenta.COSTOS,
}


def accounts_from_dataframe(df: pd.DataFrame) -> list[AccountType]:
    codigo_col = pick_column(df, ["codigo", "cuenta", "código", "cod cuenta", "cuenta contable"])
    nombre_col = pick_column(df, ["nombre", "descripcion", "descripción", "nombre cuenta"])
    tipo_col = pick_column(
        df,
        ["strnaturaleza", "tipo", "naturaleza", "clasificacion", "clasificación", "grupo"],
    )
    keys_col = pick_column(df, ["palabras", "keywords", "clave", "concepto"])
    if not codigo_col or not tipo_col:
        if not codigo_col or not nombre_col:
            raise MappingError("El plan de cuentas debe incluir columnas de código y nombre.")

    movement_col = pick_column(df, ["idmovto", "id movto", "movimiento"])
    active_col = pick_column(df, ["strvigencia", "vigencia"])

    accounts: list[AccountType] = []
    for _, row in df.iterrows():
        if movement_col and normalize_text(row.get(movement_col, "")) not in {"S", "SI", "1", "TRUE"}:
            continue
        if active_col and normalize_text(row.get(active_col, "")) not in {"S", "SI", "1", "TRUE", "ACTIVO"}:
            continue

        codigo = _account_code(row.get(codigo_col, ""))
        raw_tipo = normalize_text(row.get(tipo_col, "")) if tipo_col else ""
        naturaleza = _nature_from_label(raw_tipo)
        if naturaleza is None:
            naturaleza = _nature_from_puc_code(codigo)
        if naturaleza is None:
            continue

        accounts.append(
            AccountType(
                codigo=codigo,
                nombre=str(row.get(nombre_col, "")).strip() if nombre_col else "",
                naturaleza=naturaleza,
                palabras_clave=str(row.get(keys_col, "")).strip() if keys_col else "",
            )
        )
    if not accounts:
        raise MappingError("No se encontraron cuentas activas clasificables como VENTA, COMPRA o COSTOS.")
    logger.info("Cuentas importadas: %s", len(accounts))
    return accounts


def _nature_from_label(raw_tipo: str) -> NaturalezaCuenta | None:
    for token, value in NATURALEZA_ALIASES.items():
        if token in raw_tipo.split() or raw_tipo == token:
            return value
    return None


def _nature_from_puc_code(codigo: str) -> NaturalezaCuenta | None:
    class_nature = {
        "4": NaturalezaCuenta.VENTA,
        "5": NaturalezaCuenta.COMPRA,
        "6": NaturalezaCuenta.COSTOS,
        "7": NaturalezaCuenta.COSTOS,
    }
    return class_nature.get(codigo[:1])


def _account_code(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _expected_naturaleza(invoice: InvoiceRecord, prefer_costos: bool) -> NaturalezaCuenta:
    if invoice.tipo_reporte == TipoReporte.EMITIDAS:
        return NaturalezaCuenta.VENTA
    return NaturalezaCuenta.COSTOS if prefer_costos else NaturalezaCuenta.COMPRA


def _looks_like_cost(invoice: InvoiceRecord) -> bool:
    text = normalize_text(f"{invoice.concepto} {invoice.razon_social}")
    tokens = ("COSTO", "INVENTARIO", "MATERIA PRIMA", "MERCANCIA", "MERCANCÍA", "PRODUCCION")
    return any(token in text for token in tokens)


def _best_account(invoice: InvoiceRecord, candidates: list[AccountType]) -> AccountType | None:
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda acc: similarity_token(
            f"{invoice.concepto} {invoice.razon_social}",
            f"{acc.nombre} {acc.palabras_clave}",
        ),
        reverse=True,
    )
    return ranked[0]


def classify_invoices(
    invoices: list[InvoiceRecord],
    accounts: list[AccountType],
) -> list[ClassificationResult]:
    counts = Counter(f"{inv.nit}|{inv.numero_factura}" for inv in invoices)
    duplicates = {key for key, n in counts.items() if n > 1}

    by_nat: dict[NaturalezaCuenta, list[AccountType]] = {
        NaturalezaCuenta.VENTA: [a for a in accounts if a.naturaleza == NaturalezaCuenta.VENTA],
        NaturalezaCuenta.COMPRA: [a for a in accounts if a.naturaleza == NaturalezaCuenta.COMPRA],
        NaturalezaCuenta.COSTOS: [a for a in accounts if a.naturaleza == NaturalezaCuenta.COSTOS],
    }

    results: list[ClassificationResult] = []
    for invoice in invoices:
        prefer_costos = _looks_like_cost(invoice)
        naturaleza = _expected_naturaleza(invoice, prefer_costos)
        account = _best_account(invoice, by_nat[naturaleza])
        if account is None and naturaleza != NaturalezaCuenta.VENTA:
            fallback = NaturalezaCuenta.COMPRA if naturaleza == NaturalezaCuenta.COSTOS else NaturalezaCuenta.COSTOS
            account = _best_account(invoice, by_nat[fallback])
            if account:
                naturaleza = fallback

        flags = field_flags_for_classification(invoice, account)
        confidence = score_matches(flags)
        alerts = detect_critical(
            invoice,
            duplicates,
            classified_account=account.codigo if account else "",
            value_ok=invoice.valor_total > 0,
            date_ok=True,
        )
        critical = bool(alerts)
        status = decide_status(confidence, critical)

        if invoice.tipo_reporte == TipoReporte.EMITIDAS:
            contrapartida = settings.cuenta_cxc
            iva_cta = settings.cuenta_iva_generado
        else:
            contrapartida = settings.cuenta_cxp
            iva_cta = settings.cuenta_iva_descontable

        results.append(
            ClassificationResult(
                invoice_id=invoice.id,
                naturaleza=naturaleza if account else None,
                cuenta_principal=account.codigo if account else "",
                cuenta_contrapartida=contrapartida,
                cuenta_iva=iva_cta,
                confidence=confidence,
                status=status,
                alerts=alerts,
                matched_fields=flags,
                critical_errors=critical,
            )
        )
    return results
