from __future__ import annotations

from datetime import date
from decimal import Decimal

from core.config import settings
from core.exceptions import ValidationErrorApp
from core.logging_config import logger
from core.models import InvoiceRecord, TipoReporte
from services.excel_service import pick_column
from utils.dates import parse_date
from utils.numbers import parse_decimal
from utils.strings import digits_only, nit_without_dv

COLUMN_ALIASES = {
    "nit": [
        "nit",
        "nit receptor",
        "nit emisor",
        "identificacion",
        "nro identificacion",
        "número de identificación",
        "numero identificacion",
        "nit adquiriente",
        "nit obligado",
    ],
    "razon_social": [
        "razon social",
        "razón social",
        "nombre",
        "nombre receptor",
        "nombre emisor",
        "adquiriente",
        "cliente",
        "proveedor",
        "tercero",
    ],
    "numero": [
        "folio",
        "numero",
        "número",
        "nro factura",
        "numero factura",
        "número de factura",
        "factura",
        "consecutivo",
        "documento",
    ],
    "prefijo": ["prefijo", "prefijo factura"],
    "fecha": [
        "fecha",
        "fecha emision",
        "fecha emisión",
        "fecha factura",
        "fecha documento",
        "f. emisión",
    ],
    "total": [
        "total",
        "valor total",
        "valor a pagar",
        "importe total",
        "total factura",
        "vr total",
    ],
    "iva": ["iva", "impuesto", "valor iva", "total iva", "impuestos"],
    "base": ["base", "subtotal", "base gravable", "valor bruto", "valor sin iva"],
    "concepto": ["concepto", "descripcion", "descripción", "detalle", "observacion"],
    "cufe": ["cufe", "cude", "codigo unico"],
    "estado": ["estado", "estado factura", "estado dian"],
}


def _cell(row, column: str | None) -> str:
    if not column:
        return ""
    value = row.get(column, "")
    if value is None:
        return ""
    return str(value).strip()


def invoices_from_dataframe(df, tipo: TipoReporte) -> list[InvoiceRecord]:
    mapping = {key: pick_column(df, aliases) for key, aliases in COLUMN_ALIASES.items()}
    missing = [key for key in ("nit", "numero", "fecha", "total") if mapping[key] is None]
    if missing:
        raise ValidationErrorApp(
            "El reporte DIAN no contiene columnas obligatorias: "
            + ", ".join(missing)
            + ". Verifique el archivo de facturas emitidas o recibidas."
        )

    invoices: list[InvoiceRecord] = []
    seen: set[str] = set()
    for idx, row in df.iterrows():
        try:
            nit = nit_without_dv(_cell(row, mapping["nit"]))
            prefijo = _cell(row, mapping["prefijo"])
            numero = _cell(row, mapping["numero"])
            documento = f"{prefijo}{numero}".replace(" ", "")
            fecha = parse_date(row[mapping["fecha"]])
            total = parse_decimal(row[mapping["total"]])
            iva = parse_decimal(row[mapping["iva"]]) if mapping["iva"] else Decimal("0.00")
            base = parse_decimal(row[mapping["base"]]) if mapping["base"] else (total - iva)
            if base <= 0:
                base = total - iva if total >= iva else total

            record = InvoiceRecord(
                tipo_reporte=tipo,
                nit=nit,
                razon_social=_cell(row, mapping["razon_social"]),
                numero_factura=documento or numero,
                fecha=fecha,
                valor_total=total,
                valor_iva=iva,
                valor_base=base,
                concepto=_cell(row, mapping["concepto"]),
                prefijo=prefijo,
                cufe=_cell(row, mapping["cufe"]),
                estado_dian=_cell(row, mapping["estado"]),
                raw={str(k): ("" if v is None else str(v)) for k, v in row.items()},
            )
        except Exception as exc:
            logger.warning("Fila %s omitida: %s", idx, exc)
            continue

        key = f"{record.nit}|{record.numero_factura}|{record.fecha.isoformat()}"
        if key in seen:
            record.concepto = (record.concepto + " DUPLICADA").strip()
        seen.add(key)
        invoices.append(record)

    if not invoices:
        raise ValidationErrorApp("No se pudo estructurar ninguna factura del archivo.")
    logger.info("Estructuradas %s facturas (%s)", len(invoices), tipo.value)
    return invoices


def invoices_to_records(invoices: list[InvoiceRecord]) -> list[dict]:
    rows = []
    for inv in invoices:
        rows.append(
            {
                "id": inv.id,
                "tipo_reporte": inv.tipo_reporte.value,
                "nit": inv.nit,
                "razon_social": inv.razon_social,
                "numero_factura": inv.numero_factura,
                "fecha": inv.fecha.isoformat(),
                "valor_total": str(inv.valor_total),
                "valor_iva": str(inv.valor_iva),
                "valor_base": str(inv.valor_base),
                "concepto": inv.concepto,
                "prefijo": inv.prefijo,
                "cufe": inv.cufe,
                "estado_dian": inv.estado_dian,
            }
        )
    return rows
