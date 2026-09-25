from __future__ import annotations

import streamlit as st

from ui_state import counts_dashboard, invoices_dataframe, status_badge


def render() -> None:
    st.title("Inicio / Dashboard")
    st.write(
        "Automatiza la descarga o carga de reportes DIAN (emitidas y recibidas), "
        "la clasificación contable, la generación del archivo plano según "
        "**MODELO PLANTILLA.csv** y la validación con Human-in-the-Loop cuando "
        "la confianza es menor al 80% o hay inconsistencias críticas."
    )

    counts = counts_dashboard()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Facturas", counts["facturas"])
    c2.metric("Cuentas", counts["cuentas"])
    c3.metric("Automáticas", counts["automatico"])
    c4.metric("Requieren HITL", counts["hitl"])

    c5, c6, c7 = st.columns(3)
    c5.metric("Aprobadas HITL", counts["aprobadas"])
    c6.metric("Encontradas en software", counts["encontradas"])
    c7.metric("No encontradas", counts["no_encontradas"])

    st.subheader("Flujo operativo")
    st.markdown(
        """
1. Plataforma web DIAN: reporte **EMITIDAS** o **RECIBIDAS** (.xlsx).
2. Estructuración inicial según el software contable.
3. Carga del plan de cuentas (VENTA / COMPRA / COSTOS).
4. Clasificación y búsqueda de facturas en el software contable.
5. Revisión humana de facturas no encontradas o con alertas.
6. Validación final y comprobación de valores: `1` transacciones del día / `4` transferencia única.
7. Generación del archivo plano final (`;`, decimales con `,`, fecha `MM/DD/YYYY`) para cargarlo en el software.
        """
    )

    pipeline = st.session_state.pipeline
    st.subheader("Estado de etapas")
    cols = st.columns(4)
    items = list(pipeline.steps.items())
    for i, (key, status) in enumerate(items):
        cols[i % 4].write(f"{status_badge(status)} `{key}`")

    df = invoices_dataframe()
    if not df.empty:
        st.subheader("Facturas en memoria")
        st.dataframe(df.drop(columns=["id"]), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay facturas cargadas. Empiece por **1. Cargar reporte DIAN**.")
