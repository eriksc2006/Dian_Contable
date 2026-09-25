from __future__ import annotations

import streamlit as st

from core.config import settings
from services.audit_service import audit_service
from ui_state import set_step


def render() -> None:
    st.title("10. Configuración")
    st.write(
        "Parámetros del MVP. Las credenciales DIAN se leen de `.env` o `st.secrets`; "
        "nunca se escriben en el código fuente."
    )

    st.subheader("Motor de confianza")
    threshold = st.slider(
        "Umbral HITL",
        min_value=0.50,
        max_value=0.99,
        value=float(settings.confidence_threshold),
        step=0.01,
        help="Por debajo de este valor (por defecto 80%) la factura exige revisión humana.",
    )
    settings.confidence_threshold = float(threshold)
    st.caption(
        "Pesos: NIT 25% · Factura 25% · Fecha 15% · Valor 15% · Cuenta 10% · Descripción 10%."
    )

    st.subheader("Cuentas por defecto")
    col1, col2 = st.columns(2)
    with col1:
        settings.cuenta_cxc = st.text_input("Cuenta por cobrar (CxC)", settings.cuenta_cxc)
        settings.cuenta_ingreso_default = st.text_input("Ingreso por defecto", settings.cuenta_ingreso_default)
        settings.cuenta_iva_generado = st.text_input("IVA generado", settings.cuenta_iva_generado)
        settings.cuenta_compra_default = st.text_input("Compra por defecto", settings.cuenta_compra_default)
    with col2:
        settings.cuenta_cxp = st.text_input("Cuenta por pagar (CxP)", settings.cuenta_cxp)
        settings.cuenta_costo_default = st.text_input("Costo por defecto", settings.cuenta_costo_default)
        settings.cuenta_iva_descontable = st.text_input("IVA descontable", settings.cuenta_iva_descontable)
        settings.centro_costo_default = st.text_input("Centro de costo", settings.centro_costo_default)

    settings.comprobante_inicial = int(
        st.number_input("Comprobante inicial", min_value=1, max_value=99999, value=settings.comprobante_inicial)
    )

    st.subheader("Fase 2 · DIAN")
    st.text_input("DIAN_BASE_URL (solo lectura de entorno)", value=settings.dian_base_url, disabled=True)
    st.text_input("DIAN_USERNAME (solo lectura de entorno)", value=settings.dian_username, disabled=True)
    st.caption("La contraseña se toma de DIAN_PASSWORD / secrets y no se muestra.")

    if st.button("Reiniciar pipeline en memoria"):
        for key in [
            "invoices",
            "accounts",
            "classifications",
            "ledger_lines",
            "plain_text",
            "match_results",
            "software_rows",
            "dian_raw_df",
        ]:
            if key in st.session_state:
                if key in {"invoices", "accounts", "ledger_lines"}:
                    st.session_state[key] = []
                elif key in {"classifications", "match_results"}:
                    st.session_state[key] = {}
                elif key == "plain_text":
                    st.session_state[key] = ""
                else:
                    del st.session_state[key]
        for step in st.session_state.pipeline.steps:
            set_step(step, "pending")
        audit_service.record(
            st.session_state.pipeline.auditor,
            "RESET_PIPELINE",
            "pipeline",
            detalle="Reinicio de sesión",
        )
        st.success("Pipeline reiniciado.")
