from __future__ import annotations

import streamlit as st

from core.config import PIPELINE_STEPS
from ui_state import init_state, status_badge


FLOW_ITEMS = [
    ("cargar_dian", "1. Cargar reporte DIAN"),
    ("procesar", "2. Procesar facturas"),
    ("clasificar", "3. Clasificar facturas"),
    ("txt", "4. Generar archivo plano"),
    ("software", "5. Cruzar con software contable"),
    ("hitl", "6. Revisión humana"),
    ("validacion", "7. Validación final"),
]

PAGE_STEP_KEYS = {
    "cargar_dian": "cargar_dian",
    "procesar": "procesar",
    "clasificar": "clasificar",
    "txt": "archivo_plano",
    "software": "software_contable",
    "hitl": "hitl",
    "validacion": "validacion",
}

FLOW_KEYS = tuple(key for key, _ in FLOW_ITEMS)
OPTIONAL_PAGES = ("auditoria", "config")


def render_sidebar() -> str:
    init_state()
    if st.session_state.page == "cuentas":
        st.session_state.page = "clasificar"
    elif st.session_state.page == "inicio" or st.session_state.page not in (*FLOW_KEYS, *OPTIONAL_PAGES):
        st.session_state.page = FLOW_KEYS[0]

    st.sidebar.title("DIAN Contable")
    st.sidebar.caption("Sigue los pasos en la pantalla principal.")

    pipeline = st.session_state.pipeline
    st.sidebar.markdown("### Estado del proceso")
    for key, label in PIPELINE_STEPS:
        st.sidebar.markdown(f"{status_badge(pipeline.steps.get(key, 'pending'))}  \n{label}")
    st.sidebar.caption(
        f"Plan activo: {len(st.session_state.accounts)} cuentas · "
        f"{st.session_state.accounts_filename or 'sin cargar'}"
    )

    st.sidebar.divider()
    auditor = st.sidebar.text_input("Auditor / contador", value=pipeline.auditor)
    pipeline.auditor = auditor or "contador"
    st.session_state.pipeline = pipeline

    st.sidebar.caption("Accesos opcionales")
    st.sidebar.button(
        "Auditoría",
        use_container_width=True,
        on_click=_navigate_to,
        args=("auditoria",),
    )
    st.sidebar.button(
        "Configuración",
        use_container_width=True,
        on_click=_navigate_to,
        args=("config",),
    )
    return st.session_state.page


def page_neighbors(current: str) -> tuple[str | None, str | None]:
    if current not in FLOW_KEYS:
        return None, None
    index = FLOW_KEYS.index(current)
    previous = FLOW_KEYS[index - 1] if index > 0 else None
    following = FLOW_KEYS[index + 1] if index < len(FLOW_KEYS) - 1 else None
    return previous, following


def render_flow_progress(current: str) -> None:
    index = FLOW_KEYS.index(current)
    label = FLOW_ITEMS[index][1]
    st.caption(f"Paso {index + 1} de {len(FLOW_ITEMS)} · {label}")
    st.progress((index + 1) / len(FLOW_ITEMS))


def can_advance_step(page: str, status: str) -> bool:
    if status == "completed":
        return True
    return status == "attention" and page in {"clasificar", "software"}


def render_flow_controls(current: str, placement: str) -> None:
    previous, following = page_neighbors(current)
    if current not in FLOW_KEYS:
        return

    left, right = st.columns(2)
    status = st.session_state.pipeline.steps.get(PAGE_STEP_KEYS[current], "pending")
    can_continue = can_advance_step(current, status)

    left.button(
        "← Anterior",
        disabled=previous is None,
        use_container_width=True,
        key=f"flow_previous_{placement}",
        on_click=_navigate_to,
        args=(previous,),
    )

    right.button(
        f"Siguiente paso: {FLOW_ITEMS[FLOW_KEYS.index(following)][1]}" if following else "Proceso finalizado",
        disabled=following is None or not can_continue,
        type="primary",
        use_container_width=True,
        key=f"flow_next_{placement}",
        on_click=_navigate_to,
        args=(following,),
    )
    if following is not None and not can_continue:
        st.caption("Completa la acción de esta etapa para habilitar el siguiente paso.")
    elif following is None and can_continue:
        st.success("Proceso completado.")


def _navigate_to(page: str | None) -> None:
    if page is not None:
        st.session_state.page = page
