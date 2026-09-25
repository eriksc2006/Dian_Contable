from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from utils.numbers import parse_decimal
from utils.strings import digits_only, nit_without_dv, normalize_text


class TipoReporte(str, Enum):
    EMITIDAS = "EMITIDAS"
    RECIBIDAS = "RECIBIDAS"


class NaturalezaCuenta(str, Enum):
    VENTA = "VENTA"
    COMPRA = "COMPRA"
    COSTOS = "COSTOS"


class InvoiceStatus(str, Enum):
    PENDIENTE = "PENDIENTE"
    AUTOMATICO = "AUTOMATICO"
    REQUIERE_REVISION = "REQUIERE_REVISION"
    ERROR = "ERROR"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    OMITIDO = "OMITIDO"
    ENCONTRADA = "ENCONTRADA"
    NO_ENCONTRADA = "NO_ENCONTRADA"
    VALIDADA = "VALIDADA"


class TipoMovimiento(int, Enum):
    DEBITO = 1
    CREDITO = 2


class TipoOperacionConciliacion(str, Enum):
    TRANSACCIONES_DIA = "1"
    TRANSFERENCIA_UNICA = "4"
    SIN_MARCAR = ""


class InvoiceRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    tipo_reporte: TipoReporte
    nit: str
    razon_social: str = ""
    numero_factura: str
    fecha: date
    valor_total: Decimal
    valor_iva: Decimal = Decimal("0.00")
    valor_base: Decimal = Decimal("0.00")
    concepto: str = ""
    prefijo: str = ""
    cufe: str = ""
    estado_dian: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("nit", mode="before")
    @classmethod
    def _nit(cls, value: Any) -> str:
        return nit_without_dv(str(value or ""))

    @field_validator("numero_factura", "razon_social", "concepto", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("valor_total", "valor_iva", "valor_base", mode="before")
    @classmethod
    def _money(cls, value: Any) -> Decimal:
        return parse_decimal(value)


class AccountType(BaseModel):
    codigo: str
    nombre: str = ""
    naturaleza: NaturalezaCuenta
    palabras_clave: str = ""

    @field_validator("codigo", mode="before")
    @classmethod
    def _codigo(cls, value: Any) -> str:
        return str(value or "").strip()


class ClassificationResult(BaseModel):
    invoice_id: str
    naturaleza: NaturalezaCuenta | None = None
    cuenta_principal: str = ""
    cuenta_contrapartida: str = ""
    cuenta_iva: str = ""
    confidence: float = 0.0
    status: InvoiceStatus = InvoiceStatus.PENDIENTE
    alerts: list[str] = Field(default_factory=list)
    matched_fields: dict[str, bool] = Field(default_factory=dict)
    critical_errors: bool = False


class LedgerLine(BaseModel):
    cuenta: str
    comprobante: str
    fecha: date
    documento: str
    documento_ref: str
    nit: str
    detalle: str
    tipo: TipoMovimiento
    valor: Decimal
    base: Decimal = Decimal("0.00")
    centro_costo: str = "00"
    trans_ext: str = ""
    plazo: str = "0"
    docto_electronico: str = "0"


class MatchResult(BaseModel):
    invoice_id: str
    encontrada: bool
    confidence: float = 0.0
    status: InvoiceStatus
    alerts: list[str] = Field(default_factory=list)
    software_row: dict[str, Any] = Field(default_factory=dict)


class HitlDecision(BaseModel):
    invoice_id: str
    accion: Literal["APROBAR", "CORREGIR", "RECHAZAR", "OMITIR"]
    actor: str
    motivo: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    cambios: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str
    accion: str
    entidad: str
    entidad_id: str = ""
    detalle: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class PipelineState(BaseModel):
    steps: dict[str, str] = Field(
        default_factory=lambda: {
            "cargar_dian": "pending",
            "procesar": "pending",
            "cuentas": "pending",
            "clasificar": "pending",
            "archivo_plano": "pending",
            "software_contable": "pending",
            "hitl": "pending",
            "validacion": "pending",
        }
    )
    tipo_reporte: TipoReporte | None = None
    auditor: str = "contador"
    comprobante_inicial: int = 1
    tipo_operacion: TipoOperacionConciliacion = TipoOperacionConciliacion.SIN_MARCAR


def invoice_key(nit: str, numero: str) -> str:
    return f"{digits_only(nit)}|{normalize_text(numero)}"
