from __future__ import annotations

from pathlib import Path

from core.config import settings
from core.exceptions import DianAutomationError, DianNotConfiguredError
from core.logging_config import logger


class DianService:
    """Carga manual del reporte (MVP) y gancho de automatización Fase 2 con Playwright."""

    def is_fase2_configured(self) -> bool:
        password = settings.dian_password.get_secret_value()
        return bool(settings.dian_base_url and settings.dian_username and password)

    def download_report(self, tipo: str, dest_dir: Path) -> Path:
        if not self.is_fase2_configured():
            raise DianNotConfiguredError(
                "Fase 2 no configurada. Defina DIAN_BASE_URL, DIAN_USERNAME y "
                "DIAN_PASSWORD en .env o st.secrets y use la carga manual .xlsx."
            )
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise DianAutomationError(
                "Playwright no está instalado. Ejecute: pip install playwright && playwright install"
            ) from exc

        logger.info("Iniciando descarga Fase 2 DIAN tipo=%s", tipo)
        target = dest_dir / f"dian_{tipo.lower()}.xlsx"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=settings.dian_headless)
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()
                page.goto(settings.dian_base_url, wait_until="domcontentloaded", timeout=60000)
                # El portal DIAN (MUISCA / factura electrónica) cambia con frecuencia.
                # Esta Fase 2 deja el navegador autenticable por selectores configurables
                # en una iteración posterior; no se simula un bypass de autenticación.
                browser.close()
        except DianNotConfiguredError:
            raise
        except Exception as exc:
            raise DianAutomationError(f"No fue posible automatizar el portal DIAN: {exc}") from exc

        raise DianAutomationError(
            "La navegación Fase 2 alcanzó el portal, pero la descarga automática "
            "de reportes Emitidas/Recibidas requiere mapear los selectores oficiales "
            "de su cuenta. Use la carga manual del .xlsx mientras tanto."
        )


dian_service = DianService()
