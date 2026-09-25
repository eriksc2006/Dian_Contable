from __future__ import annotations

import pandas as pd
import streamlit as st

from core.exceptions import ValidationErrorApp
from core.models import InvoiceRecord, TipoReporte
from services.audit_service import audit_service
from services.normalization_service import invoices_from_dataframe
from ui_state import invoices_dataframe, set_step


def render() -> None:
    st.title("2. Procesar facturas")
    st.write(
        "Filtra y estructura el XLSX hacia el esquema interno (NIT sin DV, "
        "número de factura, fecha, base, IVA y total)."
    )

    if "dian_raw_df" not in st.session_state:
        st.warning("Primero cargue un reporte DIAN.")
        return

    df: pd.DataFrame = st.session_state["dian_raw_df"]
    tipo = st.session_state.pipeline.tipo_reporte or TipoReporte.EMITIDAS
    st.caption(f"Origen: {st.session_state.get('source_filename', '')} · Tipo: {tipo.value}")

    if st.button("Estructurar información", type="primary"):
        try:
            items = invoices_from_dataframe(df, tipo)
            st.session_state.invoices = items
            st.session_state.classifications = {}
            st.session_state.ledger_lines = []
            st.session_state.plain_text = ""
            st.session_state.match_results = {}
            st.session_state.software_rows = []
            st.session_state.hitl_queue_index = 0
            set_step("procesar", "completed")
            set_step("cuentas", "attention" if not st.session_state.accounts else "completed")
            for step in ("clasificar", "archivo_plano", "software_contable", "hitl", "validacion"):
                set_step(step, "pending")
            audit_service.record(
                st.session_state.pipeline.auditor,
                "PROCESAR",
                "facturas",
                detalle=f"{len(items)} facturas estructuradas",
            )
            st.success(f"Se estructuraron {len(items)} facturas.")
        except ValidationErrorApp as exc:
            set_step("procesar", "attention")
            st.error(str(exc))

    if st.session_state.invoices:
        out = invoices_dataframe()
        st.dataframe(out.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar estructurado CSV",
            out.to_csv(index=False, sep=";").encode("utf-8"),
            file_name="facturas_estructuradas.csv",
            mime="text/csv",
        )
