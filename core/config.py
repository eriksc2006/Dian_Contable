from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PLANTILLA_HEADER = (
    "Cuenta;Comprobante;Fecha(mm/dd/yyyy);Documento;Documento Ref.;NIT;"
    "Detalle;Tipo;Valor;Base;Centro de Costo;Trans. Ext;Plazo;Docto Electrónico"
)

PLANTILLA_COLUMNS = [
    "Cuenta",
    "Comprobante",
    "Fecha(mm/dd/yyyy)",
    "Documento",
    "Documento Ref.",
    "NIT",
    "Detalle",
    "Tipo",
    "Valor",
    "Base",
    "Centro de Costo",
    "Trans. Ext",
    "Plazo",
    "Docto Electrónico",
]

PIPELINE_STEPS = [
    ("cargar_dian", "1. Cargar reporte DIAN"),
    ("procesar", "2. Procesar facturas"),
    ("cuentas", "Plan de cuentas automático"),
    ("clasificar", "3. Clasificar facturas"),
    ("software_contable", "4. Software contable"),
    ("hitl", "5. Revisión humana (HITL)"),
    ("validacion", "6. Validación final"),
    ("archivo_plano", "7. Generar archivo plano"),
]

CONFIDENCE_WEIGHTS = {
    "nit": 0.25,
    "factura": 0.25,
    "fecha": 0.15,
    "valor": 0.15,
    "cuenta": 0.10,
    "descripcion": 0.10,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    auditor_default_name: str = "contador"

    cuenta_cxc: str = "130505"
    cuenta_cxp: str = "220505"
    cuenta_iva_generado: str = "24080501"
    cuenta_iva_descontable: str = "24081001"
    cuenta_ingreso_default: str = "41355602"
    cuenta_compra_default: str = "613501"
    cuenta_costo_default: str = "613502"
    centro_costo_default: str = "00"
    comprobante_inicial: int = 1

    dian_base_url: str = ""
    dian_username: str = ""
    dian_password: SecretStr = SecretStr("")
    dian_headless: bool = True

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def runtime_dir(self) -> Path:
        return self.data_dir / "runtime"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def samples_dir(self) -> Path:
        return self.data_dir / "samples"

    @property
    def audit_dir(self) -> Path:
        return self.data_dir / "audit"

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.runtime_dir,
            self.logs_dir,
            self.exports_dir,
            self.samples_dir,
            self.audit_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
