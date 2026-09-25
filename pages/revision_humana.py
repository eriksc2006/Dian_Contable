from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import streamlit as st

from core.models import InvoiceStatus, TipoReporte
from services.audit_service import audit_service
from ui_state import invoice_map, set_step
from utils.dates import parse_date
from utils.numbers import parse_decimal
from utils.strings import digits_only


HITL_STATUSES = {
    InvoiceStatus.REQUIERE_REVISION,
    InvoiceStatus.ERROR,
    InvoiceStatus.NO_ENCONTRADA,
}


def render() -> None:
    st.title("6. Revisión humana (HITL)")
    st.write(
        "Solo se muestran facturas en **REQUIERE_REVISION**, **ERROR** o **NO_ENCONTRADA**. "
        "El contador puede aprobar, corregir, rechazar u omitir. Cada acción queda en auditoría."
    )

    queue = _queue()
    if not queue:
        st.success("No hay facturas pendientes de revisión humana.")
        set_step("hitl", "completed")
        return

    set_step("hitl", "attention")
    idx = st.session_state.get("hitl_queue_index", 0) % len(queue)
    invoice, classification = queue[idx]
    st.caption(f"Pendiente {idx + 1} de {len(queue)}")

    for alert in classification.alerts:
        st.warning(alert)
    if not classification.alerts:
        st.info("Confianza insuficiente para cierre automático.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Confianza", f"{classification.confidence * 100:.0f}%")
    c2.metric("Estado", classification.status.value)
    c3.metric("Naturaleza", classification.naturaleza.value if classification.naturaleza else "N/D")

    st.subheader("Factura")
    st.json(
        {
            "NIT": invoice.nit,
            "Tercero": invoice.razon_social,
            "Factura": invoice.numero_factura,
            "Fecha": invoice.fecha.isoformat(),
            "Total": str(invoice.valor_total),
            "Base": str(invoice.valor_base),
            "IVA": str(invoice.valor_iva),
            "Cuenta": classification.cuenta_principal,
            "Campos coincidentes": classification.matched_fields,
        }
    )

    st.subheader("Corrección")
    nit = st.text_input("NIT", invoice.nit)
    cuenta = st.text_input("Cuenta contable", classification.cuenta_principal)
    fecha = st.date_input("Fecha", invoice.fecha)
    valor = st.text_input("Valor total", str(invoice.valor_total))
    motivo = st.text_area("Motivo / justificación", placeholder="Obligatorio al corregir, rechazar u omitir")

    b1, b2, b3, b4, b5 = st.columns(5)
    actor = st.session_state.pipeline.auditor

    if b1.button("Aprobar", type="primary"):
        classification.status = InvoiceStatus.APROBADO
        classification.critical_errors = False
        _log(actor, "APROBAR", invoice.id, motivo or "Aprobación HITL", {})
        _advance(len(queue))
    if b2.button("Corregir"):
        if not motivo.strip():
            st.error("Indique el motivo de la corrección.")
        else:
            cambios = {
                "nit": nit,
                "cuenta": cuenta,
                "fecha": fecha.isoformat(),
                "valor_total": valor,
            }
            invoice.nit = digits_only(nit)
            invoice.fecha = fecha
            invoice.valor_total = parse_decimal(valor)
            classification.cuenta_principal = cuenta.strip()
            classification.status = InvoiceStatus.APROBADO
            classification.critical_errors = False
            if "⚠️ Cuenta no asignada" in classification.alerts and cuenta.strip():
                classification.alerts = [a for a in classification.alerts if "Cuenta no asignada" not in a]
            _log(actor, "CORREGIR", invoice.id, motivo, cambios)
            _advance(len(queue))
    if b3.button("Rechazar"):
        if not motivo.strip():
            st.error("Indique el motivo del rechazo.")
        else:
            classification.status = InvoiceStatus.RECHAZADO
            _log(actor, "RECHAZAR", invoice.id, motivo, {})
            _advance(len(queue))
    if b4.button("Omitir"):
        classification.status = InvoiceStatus.OMITIDO
        _log(actor, "OMITIR", invoice.id, motivo or "Omitida en HITL", {})
        _advance(len(queue))
    if b5.button("Siguiente"):
        st.session_state.hitl_queue_index = (idx + 1) % len(queue)
        st.rerun()

    remaining = _queue()
    if not remaining:
        set_step("hitl", "completed")
        set_step("validacion", "attention")


def _queue():
    mapping = invoice_map()
    items = []
    for inv_id, cls in st.session_state.classifications.items():
        if cls.status in HITL_STATUSES and inv_id in mapping:
            items.append((mapping[inv_id], cls))
    return items


def _log(actor: str, accion: str, invoice_id: str, motivo: str, cambios: dict) -> None:
    audit_service.record(
        actor,
        accion,
        "hitl",
        entidad_id=invoice_id,
        detalle=motivo,
        payload={"cambios": cambios, "timestamp": datetime.utcnow().isoformat()},
    )
    st.success(f"Acción {accion} registrada.")


def _advance(queue_len: int) -> None:
    if queue_len <= 1:
        st.session_state.hitl_queue_index = 0
    else:
        st.session_state.hitl_queue_index = st.session_state.get("hitl_queue_index", 0)
    st.rerun()
