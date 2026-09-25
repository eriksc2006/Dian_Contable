from __future__ import annotations


class DianContableError(Exception):
    """Error base de la aplicación."""


class ValidationErrorApp(DianContableError):
    """Datos inválidos o incompletos."""


class MappingError(DianContableError):
    """No fue posible mapear columnas o cuentas."""


class ExportError(DianContableError):
    """Fallo al generar el archivo plano."""


class MatchingError(DianContableError):
    """Fallo en el cruce con el software contable."""


class DianNotConfiguredError(DianContableError):
    """Fase 2 DIAN no configurada (credenciales o URL ausentes)."""


class DianAutomationError(DianContableError):
    """Error durante la automatización del portal DIAN."""
