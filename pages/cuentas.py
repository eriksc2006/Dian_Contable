from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from core.config import settings
from core.exceptions import MappingError
from services.audit_service import audit_service
from services.classification_service import accounts_from_dataframe
from services.excel_service import read_tabular
from ui_state import set_step


def render() -> None:
    st.title("3. Cargar tipos de cuentas")
    st.write(
        "Importe el plan de cuentas del software. Si incluye código y nombre de cuenta, "
        "las cuentas de movimiento se clasifican automáticamente según su clase PUC."
    )

    uploaded = st.file_uploader("Plan / tipos de cuentas (.xlsx o .csv)", type=["xlsx", "xls", "csv"])
    sample = settings.samples_dir / "tipos_cuentas_sample.xlsx"
    if sample.exists() and st.button("Usar plan de cuentas de ejemplo"):
        _load(sample)

    if uploaded is not None and st.button("Importar cuentas", type="primary"):
        _load_bytes(uploaded.getvalue(), uploaded.name)

    accounts = st.session_state.accounts
    if accounts:
        st.success(f"{len(accounts)} cuentas activas.")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Código": a.codigo,
                        "Nombre": a.nombre,
                        "Naturaleza": a.naturaleza.value,
                        "Palabras clave": a.palabras_clave,
                    }
                    for a in accounts
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def _load(path: Path) -> None:
    df = read_tabular(path, path.name)
    _commit(df, path.name)


def _load_bytes(data: bytes, name: str) -> None:
    df = read_tabular(BytesIO(data), name)
    _commit(df, name)


def _commit(df, name: str) -> None:
    try:
        items = accounts_from_dataframe(df)
        st.session_state.accounts = items
        st.session_state.accounts_filename = name
        st.session_state.accounts_source_path = ""
        st.session_state.classifications = {}
        st.session_state.ledger_lines = []
        st.session_state.plain_text = ""
        st.session_state.match_results = {}
        st.session_state.software_rows = []
        st.session_state.hitl_queue_index = 0
        set_step("cuentas", "completed")
        for step in ("clasificar", "archivo_plano", "software_contable", "hitl", "validacion"):
            set_step(step, "pending")
        audit_service.record(
            st.session_state.pipeline.auditor,
            "CARGAR_CUENTAS",
            "plan_cuentas",
            detalle=f"{name} · {len(items)} cuentas",
        )
        st.success(f"Importadas {len(items)} cuentas desde {name}.")
    except MappingError as exc:
        set_step("cuentas", "attention")
        st.error(str(exc))
