from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from services.audit_service import audit_service
from services.excel_service import read_tabular
from services.matching_service import (
    index_software_rows,
    match_invoices,
    search_software_rows,
    software_base_value,
)
from services.txt_service import parse_plantilla_text
from ui_state import invoices_dataframe, set_step
from core.models import InvoiceStatus
from utils.strings import normalize_text


def render() -> None:
    st.title("4. Buscar facturas en el software contable")
    st.write(
        "Importe la respuesta del software y busque cualquier factura por su número. "
        "Una fila con **Base = 0** se marca como encontrada; las demás pasan a revisión."
    )

    if not st.session_state.invoices:
        st.warning("No hay facturas para cruzar.")
        return

    uploaded = st.file_uploader(
        "Exportación del software contable (.xlsx, .csv, .txt)",
        type=["xlsx", "xls", "csv", "txt"],
    )
    use_generated = st.checkbox(
        "Simular que el software devolvió el mismo archivo plano (todas encontradas, Base 0,00 en líneas sin IVA)",
        value=False,
        disabled=not bool(st.session_state.plain_text),
    )

    if st.button("Cruzar con software contable", type="primary"):
        try:
            if use_generated and st.session_state.plain_text:
                rows = parse_plantilla_text(st.session_state.plain_text)
                df = pd.DataFrame(rows)
            elif uploaded is not None:
                df = read_tabular(BytesIO(uploaded.getvalue()), uploaded.name)
                st.session_state.software_filename = uploaded.name
            else:
                st.error("Suba la exportación del software contable para cruzar las facturas.")
                return
            software_rows = index_software_rows(df)
            st.session_state.software_rows = software_rows
            results = match_invoices(
                st.session_state.invoices,
                st.session_state.classifications,
                software_rows,
            )
            st.session_state.match_results = {r.invoice_id: r for r in results}

            missing = [r for r in results if not r.encontrada]
            for result in results:
                cls = st.session_state.classifications.get(result.invoice_id)
                if not cls:
                    continue
                if not result.encontrada:
                    cls.status = InvoiceStatus.NO_ENCONTRADA
                    cls.critical_errors = True
                    for alert in result.alerts:
                        if alert not in cls.alerts:
                            cls.alerts.append(alert)
                elif result.status == InvoiceStatus.REQUIERE_REVISION:
                    cls.status = InvoiceStatus.REQUIERE_REVISION
                    for alert in result.alerts:
                        if alert not in cls.alerts:
                            cls.alerts.append(alert)

            if missing:
                set_step("software_contable", "attention")
                set_step("hitl", "attention")
                st.warning(
                    f"{len(missing)} factura(s) no encontradas. Pasan a revisión humana."
                )
            else:
                set_step("software_contable", "completed")
                set_step("validacion", "attention")
                st.success("Todas las facturas fueron encontradas en el software contable.")

            audit_service.record(
                st.session_state.pipeline.auditor,
                "CRUCE_SOFTWARE",
                "matching",
                detalle=f"encontradas={len(results)-len(missing)} no_encontradas={len(missing)}",
            )
        except Exception as exc:
            set_step("software_contable", "attention")
            st.error(str(exc))

    if st.session_state.match_results:
        found_count = sum(result.encontrada for result in st.session_state.match_results.values())
        st.caption(f"Coincidencias con Base = 0: {found_count} de {len(st.session_state.match_results)} facturas.")

    st.subheader("Revisión manual de facturas")
    st.caption("Busque las facturas DIAN por número o filtre todas sus filas cargadas.")
    search_number = st.text_input(
        "Buscar número de factura",
        placeholder="Escriba el número completo o una parte",
        key="software_invoice_search",
    )
    invoice_rows = invoices_dataframe()
    invoice_rows["Base software"] = [
        software_base_value(result.software_row)
        if result and result.software_row
        else ""
        for result in (
            st.session_state.match_results.get(invoice_id)
            for invoice_id in invoice_rows["id"]
        )
    ]
    if search_number.strip():
        normalized_query = normalize_text(search_number)
        invoice_rows = invoice_rows[
            invoice_rows["Factura"].map(normalize_text).str.contains(normalized_query, regex=False)
        ]

    st.caption(f"Facturas encontradas en la búsqueda: {len(invoice_rows)}")
    st.dataframe(
        invoice_rows.drop(columns=["id"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Buscar en todas las columnas del Excel contable**")
    software_query = st.text_input(
        "Dato de factura, NIT, tercero, valor u otra columna",
        placeholder="Escriba el dato que desea encontrar",
        key="software_excel_search",
    )
    if software_query.strip():
        software_matches = search_software_rows(
            st.session_state.software_rows,
            software_query,
        )
        st.markdown("**Filas coincidentes del software contable**")
        st.caption(f"Coincidencias encontradas: {len(software_matches)}")
        if software_matches:
            st.dataframe(
                pd.DataFrame(software_matches),
                use_container_width=True,
                hide_index=True,
            )
        elif not st.session_state.software_rows:
            st.info("Primero importe y cruce el archivo del software contable.")
        else:
            st.info("No hay filas del software contable que coincidan con ese dato.")
