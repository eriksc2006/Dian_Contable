from __future__ import annotations

import pandas as pd
import streamlit as st

from services.audit_service import audit_service


def render() -> None:
    st.title("9. Historial / Auditoría")
    st.write("Trazabilidad de cargas, clasificaciones, exportaciones y decisiones HITL.")

    events = audit_service.list_events(limit=1000)
    if not events:
        st.info("Aún no hay eventos de auditoría en esta instalación.")
        return

    df = pd.DataFrame(
        [
            {
                "Fecha": e.timestamp.isoformat(sep=" ", timespec="seconds"),
                "Actor": e.actor,
                "Acción": e.accion,
                "Entidad": e.entidad,
                "Id": e.entidad_id,
                "Detalle": e.detalle,
            }
            for e in events
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "Exportar auditoría CSV",
        df.to_csv(index=False, sep=";").encode("utf-8"),
        file_name="auditoria.csv",
        mime="text/csv",
    )
