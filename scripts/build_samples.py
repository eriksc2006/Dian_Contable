from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from core.config import settings


def build_samples() -> None:
    settings.ensure_dirs()
    samples = settings.samples_dir

    emitidas = pd.DataFrame(
        [
            {
                "Prefijo": "00FBCA-",
                "Folio": "49",
                "Fecha emisión": "08/20/2026",
                "NIT receptor": "901851834",
                "Razón social": "TIENDAS DE BELLEZA VIVELA SA",
                "Base gravable": "140000000,00",
                "IVA": "26600000,00",
                "Valor total": "166600000,00",
                "Concepto": "Venta de mercancía belleza",
                "CUFE": "abc123",
                "Estado": "Aceptada",
            },
            {
                "Prefijo": "SETT-",
                "Folio": "1001",
                "Fecha emisión": "08/21/2026",
                "NIT receptor": "900123456",
                "Razón social": "CLIENTE DEMO SAS",
                "Base gravable": "1000000,00",
                "IVA": "190000,00",
                "Valor total": "1190000,00",
                "Concepto": "Servicios profesionales",
                "CUFE": "def456",
                "Estado": "Aceptada",
            },
        ]
    )
    emitidas.to_excel(samples / "facturas_emitidas_sample.xlsx", index=False)

    recibidas = pd.DataFrame(
        [
            {
                "Prefijo": "FE",
                "Folio": "88",
                "Fecha emisión": "08/22/2026",
                "NIT emisor": "800000000",
                "Razón social": "PROVEEDOR INSUMOS SAS",
                "Base gravable": "500000,00",
                "IVA": "95000,00",
                "Valor total": "595000,00",
                "Concepto": "Compra de insumos de oficina",
                "CUFE": "ghi789",
                "Estado": "Aceptada",
            },
            {
                "Prefijo": "COSTO",
                "Folio": "12",
                "Fecha emisión": "08/22/2026",
                "NIT emisor": "890000001",
                "Razón social": "MATERIA PRIMA ANDINA LTDA",
                "Base gravable": "2000000,00",
                "IVA": "380000,00",
                "Valor total": "2380000,00",
                "Concepto": "Materia prima inventario",
                "CUFE": "jkl000",
                "Estado": "Aceptada",
            },
        ]
    )
    recibidas.to_excel(samples / "facturas_recibidas_sample.xlsx", index=False)

    cuentas = pd.DataFrame(
        [
            {
                "Código": "41355602",
                "Nombre": "Ventas mercancía belleza",
                "Tipo": "VENTA",
                "Palabras clave": "belleza venta mercancia",
            },
            {
                "Código": "413501",
                "Nombre": "Ingresos servicios",
                "Tipo": "VENTA",
                "Palabras clave": "servicios profesionales",
            },
            {
                "Código": "613501",
                "Nombre": "Compras insumos",
                "Tipo": "COMPRA",
                "Palabras clave": "insumos oficina compra",
            },
            {
                "Código": "613502",
                "Nombre": "Costos materia prima",
                "Tipo": "COSTOS",
                "Palabras clave": "materia prima inventario costo",
            },
        ]
    )
    cuentas.to_excel(samples / "tipos_cuentas_sample.xlsx", index=False)
    print(f"Muestras escritas en {samples}")


if __name__ == "__main__":
    build_samples()
