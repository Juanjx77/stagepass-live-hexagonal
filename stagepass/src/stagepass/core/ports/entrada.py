"""Puertos primarios (driving): lo que el mundo exterior puede pedirle a la aplicación.
Son interfaces puras expresadas con tipos del dominio."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from ..domain.modelo import Asiento, Boleto, Evento, Orden, ResultadoValidacion, SolicitudPago


@dataclass(frozen=True)
class ComandoIniciarCompra:
    evento_id: str
    asientos_ids: List[str]
    pasarela: str
    nombre_completo: str
    correo: str
    telefono_movil: str
    nacionalidad: str
    cliente_id: Optional[str] = None


@dataclass(frozen=True)
class ResultadoCompra:
    orden: Orden
    solicitud_pago: SolicitudPago


class ConsultarCatalogoUseCase(ABC):
    @abstractmethod
    def listar_eventos(self) -> List[Evento]: ...

    @abstractmethod
    def asientos_del_evento(self, evento_id: str) -> List[Asiento]: ...


class IniciarCompraUseCase(ABC):
    @abstractmethod
    def iniciar_compra(self, comando: ComandoIniciarCompra) -> ResultadoCompra: ...


class ConfirmarPagoUseCase(ABC):
    @abstractmethod
    def confirmar_pago(self, pasarela: str, notificacion: dict) -> Orden: ...


class ConsultarOrdenUseCase(ABC):
    @abstractmethod
    def obtener_orden(self, orden_id: str) -> Orden: ...

    @abstractmethod
    def boletos_de_orden(self, orden_id: str) -> List[Boleto]: ...


class ValidarBoletoUseCase(ABC):
    @abstractmethod
    def validar(self, codigo_redencion: str) -> ResultadoValidacion: ...


class LiberarBloqueosExpiradosUseCase(ABC):
    @abstractmethod
    def liberar_expirados(self) -> int: ...
