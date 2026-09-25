from __future__ import annotations

from datetime import datetime

import streamlit as st

from core.config import PLANTILLA_HEADER, settings
from core.exceptions import ExportError
from services.audit_service import audit_service
from services.txt_service import build_ledger_lines, ledger_to_csv_text, write_plain_file
from ui_state import set_step


def render() -> None:
    st.title("4. Generar archivo plano (.TXT / .CSV)")
    st.write(
        "Exporta el resultado con separador `;`, decimales con coma, fecha "
        "`MM/DD/YYYY` y partida doble (`Tipo` 1 débito / 2 crédito)."
    )
    st.code(PLANTILLA_HEADER, language="text")

    if not st.session_state.invoices or not st.session_state.classifications:
        st.warning("Clasifique las facturas antes de generar el plano.")
        return

    comprobante = st.number_input(
        "Comprobante inicial (5 dígitos)",
        min_value=1,
        max_value=99999,
        value=st.session_state.pipeline.comprobante_inicial,
    )
    st.session_state.pipeline.comprobante_inicial = int(comprobante)
    mark_found = st.checkbox(
        "Poner Base = 0,00 en líneas sin impuesto (marca de factura procesada)",
        value=True,
    )

    if st.button("Generar archivo plano", type="primary"):
        try:
            lines = build_ledger_lines(
                st.session_state.invoices,
                st.session_state.classifications,
                comprobante_inicial=int(comprobante),
            )
            text = ledger_to_csv_text(lines, mark_base_found=mark_found)
            st.session_state.ledger_lines = lines
            st.session_state.plain_text = text
            st.session_state.match_results = {}
            st.session_state.software_rows = []
            set_step("validacion", "pending")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_csv = settings.exports_dir / f"archivo_plano_{stamp}.csv"
            out_txt = settings.exports_dir / f"archivo_plano_{stamp}.txt"
            write_plain_file(text, out_csv)
            write_plain_file(text, out_txt)
            set_step("archivo_plano", "completed")
            set_step("software_contable", "attention")
            audit_service.record(
                st.session_state.pipeline.auditor,
                "GENERAR_PLANO",
                "archivo_plano",
                detalle=f"{len(lines)} líneas · {out_csv.name}",
            )
            st.success(f"Generadas {len(lines)} líneas de asiento.")
        except ExportError as exc:
            set_step("archivo_plano", "attention")
            st.error(str(exc))

    if st.session_state.plain_text:
        st.download_button(
            "Descargar CSV",
            st.session_state.plain_text.encode("utf-8"),
            file_name="MODELO_PLANTILLA_generado.csv",
            mime="text/csv",
        )
        st.download_button(
            "Descargar TXT",
            st.session_state.plain_text.encode("utf-8"),
            file_name="archivo_plano.txt",
            mime="text/plain",
        )
        st.text_area("Vista previa", st.session_state.plain_text, height=280)
