from __future__ import annotations

from io import BytesIO
from pathlib import Path

import streamlit as st

from core.config import settings
from core.exceptions import DianAutomationError, DianNotConfiguredError, ValidationErrorApp
from core.logging_config import logger
from core.models import TipoReporte
from services.audit_service import audit_service
from services.dian_service import dian_service
from services.excel_service import read_tabular
from ui_state import set_step


def render() -> None:
    st.title("1. Cargar reporte DIAN")
    st.write(
        "Seleccione el tipo de reporte de la plataforma web DIAN y suba el "
        "archivo **.xlsx** (o .csv). La automatización de descarga (Playwright) "
        "queda preparada como **Fase 2**."
    )

    tipo_label = st.radio("Tipo de reporte", ["EMITIDAS", "RECIBIDAS"], horizontal=True)
    tipo = TipoReporte(tipo_label)

    tab_upload, tab_fase2 = st.tabs(["Subir archivo", "Fase 2 · Automatizar portal"])

    with tab_upload:
        uploaded = st.file_uploader(
            "Reporte de facturas DIAN",
            type=["xlsx", "xls", "csv"],
            help="Exportación oficial de facturas emitidas o recibidas.",
        )
        sample = settings.samples_dir / (
            "facturas_emitidas_sample.xlsx" if tipo == TipoReporte.EMITIDAS else "facturas_recibidas_sample.xlsx"
        )
        if sample.exists():
            st.caption(f"Hay un archivo de ejemplo en `data/samples/{sample.name}`.")
            if st.button("Usar archivo de ejemplo"):
                _load_path(sample, tipo)

        if uploaded is not None and st.button("Cargar reporte", type="primary"):
            try:
                df = read_tabular(BytesIO(uploaded.getvalue()), uploaded.name)
                st.session_state["dian_raw_df"] = df
                st.session_state["source_filename"] = uploaded.name
                st.session_state.pipeline.tipo_reporte = tipo
                _clear_downstream_data()
                set_step("cargar_dian", "completed")
                set_step("procesar", "attention")
                set_step("cuentas", "completed" if st.session_state.accounts else "pending")
                for step in ("clasificar", "archivo_plano", "software_contable", "hitl", "validacion"):
                    set_step(step, "pending")
                audit_service.record(
                    st.session_state.pipeline.auditor,
                    "CARGAR_DIAN",
                    "reporte",
                    detalle=f"{tipo.value} · {uploaded.name} · {len(df)} filas",
                )
                st.success(f"Cargadas {len(df)} filas desde {uploaded.name}. Continúe en **Procesar facturas**.")
                st.dataframe(df.head(50), use_container_width=True)
            except Exception as exc:
                logger.exception("Carga DIAN")
                set_step("cargar_dian", "attention")
                st.error(str(exc))

    with tab_fase2:
        st.markdown(
            "La Fase 2 usa **Playwright** y credenciales de `st.secrets` o `.env` "
            "(`DIAN_BASE_URL`, `DIAN_USERNAME`, `DIAN_PASSWORD`). Nunca se guardan "
            "claves en el código."
        )
        st.write("Configurada:" , "sí" if dian_service.is_fase2_configured() else "no")
        if st.button("Intentar descarga automática"):
            try:
                dest = dian_service.download_report(tipo.value, settings.runtime_dir)
                _load_path(dest, tipo)
            except (DianNotConfiguredError, DianAutomationError) as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.error(str(exc))

    if "dian_raw_df" in st.session_state:
        with st.expander("Vista previa del archivo crudo", expanded=False):
            st.dataframe(st.session_state["dian_raw_df"].head(100), use_container_width=True)


def _load_path(path: Path, tipo: TipoReporte) -> None:
    df = read_tabular(path, path.name)
    st.session_state["dian_raw_df"] = df
    st.session_state["source_filename"] = path.name
    st.session_state.pipeline.tipo_reporte = tipo
    _clear_downstream_data()
    set_step("cargar_dian", "completed")
    set_step("procesar", "attention")
    set_step("cuentas", "completed" if st.session_state.accounts else "pending")
    for step in ("clasificar", "archivo_plano", "software_contable", "hitl", "validacion"):
        set_step(step, "pending")
    audit_service.record(
        st.session_state.pipeline.auditor,
        "CARGAR_DIAN",
        "reporte",
        detalle=f"{tipo.value} · ejemplo {path.name} · {len(df)} filas",
    )
    st.success(f"Cargadas {len(df)} filas desde {path.name}.")


def _clear_downstream_data() -> None:
    st.session_state.invoices = []
    st.session_state.classifications = {}
    st.session_state.ledger_lines = []
    st.session_state.plain_text = ""
    st.session_state.match_results = {}
    st.session_state.software_rows = []
    st.session_state.hitl_queue_index = 0
