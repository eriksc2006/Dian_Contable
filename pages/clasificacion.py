from __future__ import annotations

import pandas as pd
import streamlit as st

from core.models import InvoiceStatus
from services.audit_service import audit_service
from services.classification_service import classify_invoices
from ui_state import invoices_dataframe, set_step


def render() -> None:
    st.title("3. Clasificar facturas")
    st.write(
        "Cruza las facturas con los tipos de cuentas y asigna naturaleza "
        "VENTA / COMPRA / COSTOS. Si la confianza es menor al 80% o hay errores "
        "críticos, el estado pasa a **REQUIERE_REVISION**."
    )

    if not st.session_state.invoices:
        st.warning("No hay facturas procesadas.")
        return
    if not st.session_state.accounts:
        st.warning("Cargue primero el plan de tipos de cuentas.")
        return

    if st.button("Ejecutar clasificación y cruzado", type="primary"):
        results = classify_invoices(st.session_state.invoices, st.session_state.accounts)
        st.session_state.classifications = {r.invoice_id: r for r in results}
        st.session_state.ledger_lines = []
        st.session_state.plain_text = ""
        st.session_state.match_results = {}
        st.session_state.software_rows = []
        set_step("software_contable", "pending")
        set_step("validacion", "pending")
        hitl = sum(
            1
            for r in results
            if r.status in {InvoiceStatus.REQUIERE_REVISION, InvoiceStatus.ERROR}
        )
        set_step("clasificar", "attention" if hitl else "completed")
        if hitl:
            set_step("hitl", "attention")
        set_step("archivo_plano", "attention")
        audit_service.record(
            st.session_state.pipeline.auditor,
            "CLASIFICAR",
            "facturas",
            detalle=f"{len(results)} clasificadas · {hitl} HITL",
        )
        st.success(f"Clasificación lista. {hitl} facturas requieren revisión humana.")

    if st.session_state.classifications:
        df = invoices_dataframe()
        st.dataframe(df.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)
        auto = (df["Estado"] == InvoiceStatus.AUTOMATICO.value).sum()
        hitl = (df["Estado"] == InvoiceStatus.REQUIERE_REVISION.value).sum()
        st.metric("Automático vs HITL", f"{auto} / {hitl}")
