from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from core.models import InvoiceStatus, TipoMovimiento, TipoOperacionConciliacion
from services.audit_service import audit_service
from services.matching_service import software_base_is_zero
from services.txt_service import build_ledger_lines, ledger_to_csv_text
from ui_state import invoices_dataframe, set_step


def render() -> None:
    st.title("6. Validación final")
    st.write(
        "Comprobación manual de valores y marca de tipo de operación para la conciliación: "
        "**1** = transacciones del día · **4** = transferencia única."
    )

    if not st.session_state.invoices:
        st.warning("No hay datos para validar.")
        return

    pending_hitl = [
        c
        for c in st.session_state.classifications.values()
        if c.status in {InvoiceStatus.REQUIERE_REVISION, InvoiceStatus.ERROR, InvoiceStatus.NO_ENCONTRADA}
    ]
    if pending_hitl:
        st.error(
            f"Hay {len(pending_hitl)} facturas sin cerrar en HITL. "
            "No se puede finalizar el proceso."
        )
        set_step("validacion", "attention")
        return

    tipo = st.radio(
        "Tipo de operación (conciliación)",
        options=["1", "4"],
        format_func=lambda x: "1 — Transacciones del día" if x == "1" else "4 — Transferencia única",
        horizontal=True,
    )
    st.session_state.pipeline.tipo_operacion = TipoOperacionConciliacion(tipo)

    lines = st.session_state.ledger_lines
    if not lines and st.session_state.classifications:
        try:
            lines = build_ledger_lines(
                st.session_state.invoices,
                st.session_state.classifications,
                comprobante_inicial=st.session_state.pipeline.comprobante_inicial,
            )
            st.session_state.ledger_lines = lines
        except Exception as exc:
            st.error(str(exc))
            return

    debitos = sum((x.valor for x in lines if x.tipo == TipoMovimiento.DEBITO), Decimal("0"))
    creditos = sum((x.valor for x in lines if x.tipo == TipoMovimiento.CREDITO), Decimal("0"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Débitos (Tipo 1)", f"{debitos:,.2f}")
    c2.metric("Créditos (Tipo 2)", f"{creditos:,.2f}")
    c3.metric("Diferencia", f"{(debitos - creditos):,.2f}")

    balanced = abs(debitos - creditos) <= Decimal("0.05")
    if balanced:
        st.success("Partida doble cuadrada.")
    else:
        st.error("Los asientos no cuadran. Revise cuentas y valores.")

    st.dataframe(
        invoices_dataframe().drop(columns=["id"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Cerrar proceso (FIN)", type="primary", disabled=not balanced):
        for inv in st.session_state.invoices:
            cls = st.session_state.classifications.get(inv.id)
            if cls and cls.status in {InvoiceStatus.AUTOMATICO, InvoiceStatus.APROBADO, InvoiceStatus.ENCONTRADA}:
                cls.status = InvoiceStatus.VALIDADA
        set_step("validacion", "completed")
        audit_service.record(
            st.session_state.pipeline.auditor,
            "VALIDACION_FINAL",
            "pipeline",
            detalle=f"tipo_operacion={tipo} lineas={len(lines)}",
        )
        st.balloons()
        st.success("FIN DEL PROCESO. Historial disponible en Auditoría.")

        text = ledger_to_csv_text(lines)
        st.download_button(
            "Descargar archivo plano validado",
            text.encode("utf-8"),
            file_name=f"plano_validado_tipo_{tipo}.csv",
            mime="text/csv",
        )

    if st.session_state.pipeline.steps.get("validacion") == "completed":
        zero_base_rows = [
            row
            for row in st.session_state.get("software_rows", [])
            if software_base_is_zero(row)
        ]
        st.subheader("Resultado final · filas con Base = 0")
        st.metric("Filas del software con Base en cero", len(zero_base_rows))
        if zero_base_rows:
            st.dataframe(pd.DataFrame(zero_base_rows), use_container_width=True, hide_index=True)
            st.download_button(
                "Descargar filas con Base = 0",
                pd.DataFrame(zero_base_rows).to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name="facturas_base_cero.csv",
                mime="text/csv",
            )
        else:
            st.info("El cruce todavía no tiene filas del software con Base = 0.")
