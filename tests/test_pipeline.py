from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from core.models import AccountType, InvoiceRecord, InvoiceStatus, NaturalezaCuenta, TipoReporte
from services.classification_service import accounts_from_dataframe, classify_invoices
from services.matching_service import index_software_rows, match_invoices, software_base_is_zero
from services.confidence_service import (
    decide_status,
    detect_critical,
    field_flags_for_classification,
    score_matches,
)
from services.normalization_service import invoices_from_dataframe
from services.txt_service import (
    build_ledger_lines,
    ledger_to_csv_text,
    parse_plantilla_text,
)
from core.config import PLANTILLA_COLUMNS as HEADER_COLS
from navigation import FLOW_KEYS, can_advance_step, page_neighbors
from utils.dates import format_date_mmddyyyy, parse_date
from utils.numbers import format_decimal_co, parse_decimal


def test_parse_and_format_decimal_co():
    assert format_decimal_co(parse_decimal("166600000,00")) == "166600000,00"
    assert format_decimal_co(Decimal("0")) == "0,00"
    assert parse_decimal("1.190.000,50") == Decimal("1190000.50")


def test_date_mmddyyyy():
    assert parse_date("08/20/2026") == date(2026, 8, 20)
    assert format_date_mmddyyyy(date(2026, 8, 20)) == "08/20/2026"
    assert parse_date("2026-08-21") == date(2026, 8, 21)


def test_confidence_threshold_79_hitl_80_automatic():
    assert decide_status(0.79, False) == InvoiceStatus.REQUIERE_REVISION
    assert decide_status(0.80, False) == InvoiceStatus.AUTOMATICO
    assert decide_status(0.99, True) == InvoiceStatus.REQUIERE_REVISION


def test_confidence_weights_sum_to_one():
    flags = {k: True for k in ("nit", "factura", "fecha", "valor", "cuenta", "descripcion")}
    assert score_matches(flags) == 1.0
    flags["descripcion"] = False
    assert score_matches(flags) == 0.90


def test_linear_page_navigation_neighbors():
    assert page_neighbors("cargar_dian") == (None, "procesar")
    assert page_neighbors("procesar") == ("cargar_dian", "clasificar")
    assert page_neighbors("validacion") == ("hitl", None)
    assert "cuentas" not in FLOW_KEYS


def test_linear_flow_gates_unfinished_steps():
    assert not can_advance_step("procesar", "pending")
    assert can_advance_step("procesar", "completed")
    assert can_advance_step("clasificar", "attention")
    assert can_advance_step("software", "attention")
    assert not can_advance_step("hitl", "attention")


def test_critical_missing_nit_and_duplicates():
    inv = InvoiceRecord(
        tipo_reporte=TipoReporte.EMITIDAS,
        nit="",
        numero_factura="",
        fecha=date(2026, 8, 20),
        valor_total=Decimal("100.00"),
        razon_social="X",
    )
    alerts = detect_critical(inv, duplicates={"|"}, classified_account="")
    assert any("NIT" in a for a in alerts)
    assert any("Número de Factura" in a for a in alerts)
    assert any("duplicada" in a.lower() for a in alerts)
    assert any("Cuenta no asignada" in a for a in alerts)


def _sale_invoice(**kwargs) -> InvoiceRecord:
    data = dict(
        tipo_reporte=TipoReporte.EMITIDAS,
        nit="901851834",
        razon_social="TIENDAS DE BELLEZA VIVELA SA",
        numero_factura="00FBCA-49",
        fecha=date(2026, 8, 20),
        valor_total=Decimal("166600000.00"),
        valor_iva=Decimal("26600000.00"),
        valor_base=Decimal("140000000.00"),
        concepto="Venta de mercancía belleza",
    )
    data.update(kwargs)
    return InvoiceRecord(**data)


def test_classification_description_flag_is_boolean_without_keywords():
    invoice = _sale_invoice(concepto="", razon_social="Cliente sin coincidencias")
    account = AccountType(
        codigo="41355602",
        nombre="Ventas generales",
        naturaleza=NaturalezaCuenta.VENTA,
    )

    flags = field_flags_for_classification(invoice, account)
    result = classify_invoices([invoice], [account])[0]

    assert flags["descripcion"] is False
    assert result.matched_fields["descripcion"] is False


def test_double_entry_and_plantilla_14_columns():
    invoice = _sale_invoice()
    accounts = [
        AccountType(
            codigo="41355602",
            nombre="Ventas mercancía belleza",
            naturaleza=NaturalezaCuenta.VENTA,
            palabras_clave="belleza",
        )
    ]
    results = classify_invoices([invoice], accounts)
    mapping = {r.invoice_id: r for r in results}
    mapping[invoice.id].cuenta_principal = "41355602"
    mapping[invoice.id].status = InvoiceStatus.AUTOMATICO
    lines = build_ledger_lines([invoice], mapping, comprobante_inicial=3)
    text = ledger_to_csv_text(lines)
    parsed = parse_plantilla_text(text)
    assert list(parsed[0].keys()) == HEADER_COLS
    assert len(HEADER_COLS) == 14
    rows = text.strip().splitlines()
    assert rows[0] == (
        "Cuenta;Comprobante;Fecha(mm/dd/yyyy);Documento;Documento Ref.;NIT;"
        "Detalle;Tipo;Valor;Base;Centro de Costo;Trans. Ext;Plazo;Docto Electrónico"
    )
    first = rows[1].split(";")
    assert first[0] == "130505"
    assert first[1] == "00003"
    assert first[2] == "08/20/2026"
    assert first[3] == "00FBCA-49"
    assert first[5] == "901851834"
    assert first[7] == "1"
    assert first[8] == "166600000,00"
    assert first[9] == "0,00"
    iva = [ln for ln in rows[1:] if ln.startswith("24080501")][0].split(";")
    assert iva[7] == "2"
    assert iva[8] == "26600000,00"
    assert iva[9] == "140000000,00"


def test_modelo_plantilla_sample_parses():
    from pathlib import Path
    from core.config import settings

    path = settings.samples_dir / "MODELO PLANTILLA.csv"
    text = path.read_text(encoding="utf-8")
    rows = parse_plantilla_text(text)
    assert len(rows) == 3
    assert rows[0]["Cuenta"] == "130505"
    assert rows[2]["Base"] == "140000000,00"


def test_normalize_dian_excel_like_dataframe():
    df = pd.DataFrame(
        [
            {
                "NIT receptor": "901851834",
                "Razón social": "TIENDAS DE BELLEZA VIVELA SA",
                "Prefijo": "00FBCA-",
                "Folio": "49",
                "Fecha emisión": "08/20/2026",
                "Valor total": "166600000,00",
                "IVA": "26600000,00",
                "Base gravable": "140000000,00",
            }
        ]
    )
    items = invoices_from_dataframe(df, TipoReporte.EMITIDAS)
    assert items[0].nit == "901851834"
    assert items[0].numero_factura == "00FBCA-49"
    assert items[0].valor_total == Decimal("166600000.00")


def test_accounts_from_plan():
    df = pd.DataFrame(
        [
            {"Código": "41355602", "Nombre": "Ventas", "Tipo": "VENTA"},
            {"Código": "613501", "Nombre": "Compras", "Tipo": "COMPRA"},
            {"Código": "613502", "Nombre": "Costos", "Tipo": "COSTOS"},
        ]
    )
    acc = accounts_from_dataframe(df)
    assert {a.naturaleza for a in acc} == {
        NaturalezaCuenta.VENTA,
        NaturalezaCuenta.COMPRA,
        NaturalezaCuenta.COSTOS,
    }


def test_accounts_from_software_plan_uses_active_movement_accounts():
    df = pd.DataFrame(
        [
            {"Cuenta": 4, "Nombre": "INGRESOS", "IdMovto": "N", "StrVigencia": "S"},
            {"Cuenta": 41355602, "Nombre": "Ventas", "IdMovto": "S", "StrVigencia": "S"},
            {"Cuenta": 513505, "Nombre": "Gastos", "IdMovto": "S", "StrVigencia": "S"},
            {"Cuenta": 613501, "Nombre": "Costos", "IdMovto": "S", "StrVigencia": "S"},
            {"Cuenta": 110505, "Nombre": "Caja", "IdMovto": "S", "StrVigencia": "S"},
            {"Cuenta": 413557, "Nombre": "Inactiva", "IdMovto": "S", "StrVigencia": "N"},
        ]
    )

    accounts = accounts_from_dataframe(df)

    assert [(account.codigo, account.naturaleza) for account in accounts] == [
        ("41355602", NaturalezaCuenta.VENTA),
        ("513505", NaturalezaCuenta.COMPRA),
        ("613501", NaturalezaCuenta.COSTOS),
    ]


def test_matching_uses_exact_invoice_row_and_requires_zero_software_base():
    invoice = _sale_invoice()
    account = AccountType(
        codigo="41355602",
        nombre="Ventas mercancía belleza",
        naturaleza=NaturalezaCuenta.VENTA,
        palabras_clave="belleza",
    )
    classifications = {item.invoice_id: item for item in classify_invoices([invoice], [account])}
    rows = index_software_rows(
        pd.DataFrame(
            [
                {
                    "NIT": invoice.nit,
                    "Documento": invoice.numero_factura,
                    "Fecha": "08/19/2026",
                    "Valor": "1,00",
                    "Cuenta": "999999",
                    "Detalle": "Sin coincidencia",
                    "Base": "140000000,00",
                },
                {
                    "NIT": invoice.nit,
                    "Documento": "OTRA-FACTURA",
                    "Fecha": "08/20/2026",
                    "Valor": "166600000,00",
                    "Cuenta": account.codigo,
                    "Detalle": invoice.razon_social,
                    "Base": "0,00",
                },
            ]
        )
    )

    result = match_invoices([invoice], classifications, rows)[0]

    assert result.software_row["documento"] == invoice.numero_factura
    assert not result.encontrada
    assert software_base_is_zero({"Base": 0.0})
    assert software_base_is_zero({"Base": "0,00"})
    assert not software_base_is_zero({"Base": "140000000,00"})
    assert not software_base_is_zero({"Base": ""})

    rows[0]["Base"] = "0,00"
    zero_base_result = match_invoices([invoice], classifications, rows)[0]
    assert zero_base_result.encontrada
    assert zero_base_result.software_row["documento"] == invoice.numero_factura
