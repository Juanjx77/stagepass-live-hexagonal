"""Adaptadores de utilidades del sistema (reloj y generador de identificadores)."""
import uuid
from datetime import datetime, timezone

from stagepass.core.ports.salida import GeneradorIdentificadoresPuerto, RelojPuerto


class RelojSistema(RelojPuerto):
    def ahora(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)  # UTC sin zona, como lo guarda Mongo


class GeneradorUuid(GeneradorIdentificadoresPuerto):
    def nuevo_id(self) -> str:
        return uuid.uuid4().hex[:12]
