from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import settings
from core.logging_config import logger
from core.models import AuditEvent


class AuditService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (settings.audit_dir / "audit.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        actor: str,
        accion: str,
        entidad: str,
        entidad_id: str = "",
        detalle: str = "",
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor=actor,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
            payload=payload or {},
        )
        line = event.model_dump_json()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        logger.info("AUDIT %s %s %s %s", actor, accion, entidad, entidad_id)
        return event

    def list_events(self, limit: int = 500) -> list[AuditEvent]:
        if not self.path.exists():
            return []
        events: list[AuditEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(AuditEvent.model_validate(json.loads(line)))
                except Exception:
                    continue
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]


audit_service = AuditService()
