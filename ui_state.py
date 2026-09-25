from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd
import streamlit as st

from core.config import PIPELINE_STEPS, settings
from core.exceptions import MappingError
from core.models import (
    AccountType,
    ClassificationResult,
    InvoiceRecord,
    InvoiceStatus,
    MatchResult,
    PipelineState,
    TipoReporte,
)
from services.classification_service import accounts_from_dataframe
from services.excel_service import read_tabular


def init_state() -> None:
    defaults: dict[str, Any] = {
        "pipeline": PipelineState(auditor=settings.auditor_default_name),
        "invoices": [],
        "accounts": [],
        "classifications": {},
        "ledger_lines": [],
        "plain_text": "",
        "match_results": {},
        "software_rows": [],
        "hitl_queue_index": 0,
        "page": "cargar_dian",
        "source_filename": "",
        "accounts_filename": "",
        "accounts_source_path": "",
        "software_filename": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(value) if not isinstance(value, (str, int)) else value
    _ensure_default_accounts()


def _ensure_default_accounts() -> None:
    plan_path = settings.data_dir.parent / "archivos" / "Plan_de_Cuentas_v2.xlsx"
    if not plan_path.is_file():
        st.session_state.default_accounts_error = f"No se encontró el plan de cuentas: {plan_path}"
        return
    source_path = str(plan_path.resolve())
    if st.session_state.accounts_source_path == source_path and st.session_state.accounts:
        st.session_state.pop("default_accounts_error", None)
        return

    try:
        frame = read_tabular(plan_path, plan_path.name)
        loaded_accounts = accounts_from_dataframe(frame)
    except (MappingError, OSError, ValueError) as exc:
        st.session_state.default_accounts_error = f"No se pudo cargar el plan de cuentas: {exc}"
        return

    st.session_state.accounts = loaded_accounts
    st.session_state.accounts_filename = plan_path.name
    st.session_state.accounts_source_path = source_path
    st.session_state.classifications = {}
    st.session_state.ledger_lines = []
    st.session_state.plain_text = ""
    st.session_state.match_results = {}
    st.session_state.software_rows = []
    st.session_state.hitl_queue_index = 0
    pipeline = st.session_state.pipeline
    pipeline.steps["cuentas"] = "completed"
    for step in ("clasificar", "archivo_plano", "software_contable", "hitl", "validacion"):
        pipeline.steps[step] = "pending"
    st.session_state.pipeline = pipeline
    if st.session_state.invoices:
        st.session_state.page = "clasificar"
    st.session_state.pop("default_accounts_error", None)


def set_step(step: str, status: str) -> None:
    pipeline: PipelineState = st.session_state.pipeline
    pipeline.steps[step] = status
    st.session_state.pipeline = pipeline


def invoices() -> list[InvoiceRecord]:
    return st.session_state.invoices


def accounts() -> list[AccountType]:
    return st.session_state.accounts


def classifications() -> dict[str, ClassificationResult]:
    return st.session_state.classifications


def invoice_map() -> dict[str, InvoiceRecord]:
    return {inv.id: inv for inv in invoices()}


def status_badge(status: str) -> str:
    return {
        "completed": "✅ Completado",
        "attention": "⚠️ Requiere atención",
        "pending": "⬜ Pendiente",
    }.get(status, "⬜ Pendiente")


def invoices_dataframe(items: list[InvoiceRecord] | None = None) -> pd.DataFrame:
    rows = []
    for inv in items or invoices():
        cls = classifications().get(inv.id)
        match = st.session_state.match_results.get(inv.id)
        rows.append(
            {
                "id": inv.id,
                "Tipo": inv.tipo_reporte.value,
                "NIT": inv.nit,
                "Tercero": inv.razon_social,
                "Factura": inv.numero_factura,
                "Fecha": inv.fecha.isoformat(),
                "Total": float(inv.valor_total),
                "Base": float(inv.valor_base),
                "IVA": float(inv.valor_iva),
                "Naturaleza": cls.naturaleza.value if cls and cls.naturaleza else "",
                "Cuenta": cls.cuenta_principal if cls else "",
                "Confianza": round((cls.confidence if cls else 0) * 100, 1),
                "Estado": cls.status.value if cls else InvoiceStatus.PENDIENTE.value,
                "Alertas": " | ".join(cls.alerts) if cls else "",
                "En software": "SÍ" if match and match.encontrada else ("NO" if match else ""),
            }
        )
    return pd.DataFrame(rows)


def counts_dashboard() -> dict[str, int]:
    cls = list(classifications().values())
    matches = list(st.session_state.match_results.values())
    return {
        "facturas": len(invoices()),
        "cuentas": len(accounts()),
        "automatico": sum(1 for c in cls if c.status == InvoiceStatus.AUTOMATICO),
        "hitl": sum(
            1
            for c in cls
            if c.status in {InvoiceStatus.REQUIERE_REVISION, InvoiceStatus.ERROR}
        ),
        "aprobadas": sum(1 for c in cls if c.status == InvoiceStatus.APROBADO),
        "encontradas": sum(1 for m in matches if m.encontrada),
        "no_encontradas": sum(1 for m in matches if not m.encontrada),
    }
