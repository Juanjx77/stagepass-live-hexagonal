"""Adaptadores SIMULADOS de notificación (SendGrid y WhatsApp): guardan los mensajes en una bandeja."""
import logging
from typing import List, Tuple

from stagepass.core.domain.modelo import Cliente, Mensaje
from stagepass.core.ports.salida import NotificacionPuerto

log = logging.getLogger("stagepass.notificaciones")


class _Simulado(NotificacionPuerto):
    _CANAL = ""

    def __init__(self):
        self.bandeja: List[Tuple[str, Mensaje]] = []

    def canal(self) -> str:
        return self._CANAL

    def _destino(self, cliente: Cliente) -> str:
        raise NotImplementedError

    def enviar(self, destinatario: Cliente, mensaje: Mensaje) -> None:
        destino = self._destino(destinatario)
        self.bandeja.append((destino, mensaje))
        log.info("[%s] -> %s: %s", self._CANAL, destino, mensaje.asunto)


class SendgridCorreoSimulado(_Simulado):
    _CANAL = "correo"

    def _destino(self, cliente: Cliente) -> str:
        return cliente.correo


class WhatsAppSimulado(_Simulado):
    _CANAL = "whatsapp"

    def _destino(self, cliente: Cliente) -> str:
        return cliente.telefono_movil
