from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from core.config import settings  # noqa: E402
from core.logging_config import logger  # noqa: E402
from navigation import (  # noqa: E402
    FLOW_KEYS,
    render_flow_controls,
    render_flow_progress,
    render_sidebar,
)
from pages import (  # noqa: E402
    auditoria,
    cargar_dian,
    clasificacion,
    configuracion,
    cuentas,
    inicio,
    procesamiento,
    revision_humana,
    software_contable,
    txt,
    validacion,
)

st.set_page_config(
    page_title="DIAN Contable",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

settings.ensure_dirs()
logger.info("Aplicación iniciada")

ROUTES = {
    "inicio": inicio.render,
    "cargar_dian": cargar_dian.render,
    "procesar": procesamiento.render,
    "cuentas": cuentas.render,
    "clasificar": clasificacion.render,
    "txt": txt.render,
    "software": software_contable.render,
    "hitl": revision_humana.render,
    "validacion": validacion.render,
    "auditoria": auditoria.render,
    "config": configuracion.render,
}

page = render_sidebar()
if st.session_state.get("default_accounts_error"):
    st.error(st.session_state.default_accounts_error)

if page in FLOW_KEYS:
    render_flow_progress(page)
    render_flow_controls(page, "top")

ROUTES.get(page, cargar_dian.render)()

if page in FLOW_KEYS:
    st.divider()
    render_flow_controls(page, "bottom")
else:
    st.button(
        "Volver al proceso paso a paso",
        type="primary",
        on_click=lambda: st.session_state.update(page=FLOW_KEYS[0]),
    )
