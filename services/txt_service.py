from __future__ import annotations

from decimal import Decimal
from io import StringIO
from pathlib import Path

from core.config import PLANTILLA_COLUMNS, PLANTILLA_HEADER, settings
from core.exceptions import ExportError
from core.logging_config import logger
from core.models import (
    ClassificationResult,
    InvoiceRecord,
    LedgerLine,
    TipoMovimiento,
    TipoReporte,
)
from utils.dates import format_date_mmddyyyy
from utils.numbers import format_decimal_co, parse_decimal
from utils.strings import pad_comprobante


def build_ledger_lines(
    invoices: list[InvoiceRecord],
    classifications: dict[str, ClassificationResult],
    comprobante_inicial: int | None = None,
    centro_costo: str | None = None,
) -> list[LedgerLine]:
    start = comprobante_inicial if comprobante_inicial is not None else settings.comprobante_inicial
    centro = centro_costo if centro_costo is not None else settings.centro_costo_default
    lines: list[LedgerLine] = []

    for offset, invoice in enumerate(invoices):
        result = classifications.get(invoice.id)
        if not result or not result.cuenta_principal:
            continue
        if result.status.value in {"RECHAZADO", "OMITIDO"}:
            continue

        comprobante = pad_comprobante(start + offset)
        documento = invoice.numero_factura
        detalle = invoice.razon_social or invoice.concepto or "TERCERO"
        iva = parse_decimal(invoice.valor_iva)
        base = parse_decimal(invoice.valor_base)
        total = parse_decimal(invoice.valor_total)
        if base <= 0:
            base = total - iva if total >= iva else total

        common = dict(
            comprobante=comprobante,
            fecha=invoice.fecha,
            documento=documento,
            documento_ref=documento,
            nit=invoice.nit,
            detalle=detalle[:120],
            centro_costo=centro or " ",
            trans_ext="",
            plazo="0",
            docto_electronico="0",
        )

        if invoice.tipo_reporte == TipoReporte.EMITIDAS:
            lines.append(
                LedgerLine(
                    cuenta=result.cuenta_contrapartida or settings.cuenta_cxc,
                    tipo=TipoMovimiento.DEBITO,
                    valor=total,
                    base=Decimal("0.00"),
                    **common,
                )
            )
            lines.append(
                LedgerLine(
                    cuenta=result.cuenta_principal,
                    tipo=TipoMovimiento.CREDITO,
                    valor=base,
                    base=Decimal("0.00"),
                    **common,
                )
            )
            if iva > 0:
                lines.append(
                    LedgerLine(
                        cuenta=result.cuenta_iva or settings.cuenta_iva_generado,
                        tipo=TipoMovimiento.CREDITO,
                        valor=iva,
                        base=base,
                        **common,
                    )
                )
        else:
            lines.append(
                LedgerLine(
                    cuenta=result.cuenta_principal,
                    tipo=TipoMovimiento.DEBITO,
                    valor=base,
                    base=Decimal("0.00"),
                    **common,
                )
            )
            if iva > 0:
                lines.append(
                    LedgerLine(
                        cuenta=result.cuenta_iva or settings.cuenta_iva_descontable,
                        tipo=TipoMovimiento.DEBITO,
                        valor=iva,
                        base=base,
                        **common,
                    )
                )
            lines.append(
                LedgerLine(
                    cuenta=result.cuenta_contrapartida or settings.cuenta_cxp,
                    tipo=TipoMovimiento.CREDITO,
                    valor=total,
                    base=Decimal("0.00"),
                    **common,
                )
            )
    if not lines:
        raise ExportError("No hay asientos para exportar. Clasifique y apruebe facturas primero.")
    _assert_balanced(lines)
    return lines


def _assert_balanced(lines: list[LedgerLine]) -> None:
    by_comp: dict[str, list[LedgerLine]] = {}
    for line in lines:
        by_comp.setdefault(line.comprobante, []).append(line)
    for comprobante, group in by_comp.items():
        debitos = sum((x.valor for x in group if x.tipo == TipoMovimiento.DEBITO), Decimal("0.00"))
        creditos = sum((x.valor for x in group if x.tipo == TipoMovimiento.CREDITO), Decimal("0.00"))
        if abs(debitos - creditos) > Decimal("0.05"):
            raise ExportError(
                f"Comprobante {comprobante} descuadrado: débitos {debitos} vs créditos {creditos}"
            )


def ledger_to_csv_text(lines: list[LedgerLine], mark_base_found: bool = False) -> str:
    buffer = StringIO()
    buffer.write(PLANTILLA_HEADER + "\n")
    for line in lines:
        base_value = Decimal("0.00") if (mark_base_found and line.base == 0) else line.base
        row = [
            line.cuenta,
            line.comprobante,
            format_date_mmddyyyy(line.fecha),
            line.documento,
            line.documento_ref,
            line.nit,
            line.detalle,
            str(int(line.tipo.value)),
            format_decimal_co(line.valor),
            format_decimal_co(base_value),
            line.centro_costo if line.centro_costo else " ",
            line.trans_ext,
            line.plazo,
            line.docto_electronico,
        ]
        if len(row) != 14:
            raise ExportError("El archivo plano debe tener exactamente 14 columnas.")
        buffer.write(";".join(row) + "\n")
    return buffer.getvalue()


def write_plain_file(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    logger.info("Archivo plano generado: %s", path)
    return path


def parse_plantilla_text(text: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ExportError("Archivo plano vacío")
    header = lines[0].strip()
    expected = PLANTILLA_HEADER
    if header.replace(" ", "") != expected.replace(" ", ""):
        cols = [c.strip() for c in header.split(";")]
        if cols != PLANTILLA_COLUMNS:
            raise ExportError("El encabezado no coincide con MODELO PLANTILLA.csv")
    rows = []
    for line in lines[1:]:
        parts = line.split(";")
        if len(parts) < 14:
            parts.extend([""] * (14 - len(parts)))
        rows.append(dict(zip(PLANTILLA_COLUMNS, parts[:14])))
    return rows
