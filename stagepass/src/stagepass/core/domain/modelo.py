"""Modelo de dominio de StagePass Live: objetos puros del lenguaje, sin anotaciones técnicas."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from .excepciones import TransicionOrdenInvalida


class TipoEvento(Enum):
    CONCIERTO = "CONCIERTO"
    TEATRO = "TEATRO"
    FESTIVAL = "FESTIVAL"


class EstadoEvento(Enum):
    PROGRAMADO = "PROGRAMADO"
    AGOTADO = "AGOTADO"
    CANCELADO = "CANCELADO"


class EstadoAsiento(Enum):
    DISPONIBLE = "DISPONIBLE"
    BLOQUEADO = "BLOQUEADO"
    VENDIDO = "VENDIDO"


class EstadoOrden(Enum):
    PENDIENTE_PAGO = "PENDIENTE_PAGO"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"
    EXPIRADA = "EXPIRADA"


class EstadoPago(Enum):
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    PENDIENTE = "PENDIENTE"


@dataclass(frozen=True)
class Evento:
    id: str
    nombre: str
    tipo: TipoEvento
    recinto_id: str
    fecha_hora: datetime
    estado: EstadoEvento


@dataclass
class Asiento:
    id: str
    recinto_id: str
    codigo_ubicacion: str
    precio_base: Decimal
    estado: EstadoAsiento = EstadoAsiento.DISPONIBLE


@dataclass(frozen=True)
class Cliente:
    id: str
    nombre_completo: str
    correo: str
    telefono_movil: str
    nacionalidad: str


@dataclass
class Orden:
    """Reserva / orden de compra. Mientras está pendiente, sus asientos quedan bloqueados."""
    id: str
    evento_id: str
    cliente: Cliente
    asientos: List[Asiento]
    tarifa_servicio: Decimal
    descuento: Decimal
    monto_total: Decimal
    expira_en: datetime
    estado: EstadoOrden = EstadoOrden.PENDIENTE_PAGO
    referencia_pago: Optional[str] = None
    numero_factura: Optional[str] = None

    def asientos_ids(self) -> List[str]:
        return [a.id for a in self.asientos]

    def esta_expirada(self, ahora: datetime) -> bool:
        return self.estado == EstadoOrden.PENDIENTE_PAGO and ahora >= self.expira_en

    def bloquea_asientos(self, ahora: datetime) -> bool:
        return self.estado == EstadoOrden.PENDIENTE_PAGO and ahora < self.expira_en

    def vende_asientos(self) -> bool:
        return self.estado == EstadoOrden.APROBADA

    def aprobar(self, referencia: Optional[str] = None) -> None:
        self._exigir_pendiente("aprobar")
        self.estado = EstadoOrden.APROBADA
        if referencia:
            self.referencia_pago = referencia

    def rechazar(self) -> None:
        self._exigir_pendiente("rechazar")
        self.estado = EstadoOrden.RECHAZADA

    def expirar(self) -> None:
        self._exigir_pendiente("expirar")
        self.estado = EstadoOrden.EXPIRADA

    def _exigir_pendiente(self, accion: str) -> None:
        if self.estado != EstadoOrden.PENDIENTE_PAGO:
            raise TransicionOrdenInvalida(
                f"No se puede {accion} una orden en estado {self.estado.value}")


@dataclass(frozen=True)
class Boleto:
    id: str
    orden_id: str
    evento_id: str
    asiento_id: str
    codigo_redencion: str
    firma_hash: str
    fecha_emision: datetime


# ---- Objetos de valor que cruzan los puertos (tipos del dominio, nunca de una tecnología) ----

@dataclass(frozen=True)
class ResultadoTarifa:
    subtotal: Decimal
    tarifa_servicio: Decimal
    descuento: Decimal
    total: Decimal


@dataclass(frozen=True)
class SolicitudPago:
    referencia: str
    url_pago: str


@dataclass(frozen=True)
class ConfirmacionPago:
    orden_id: str
    estado: EstadoPago
    referencia: str


@dataclass(frozen=True)
class Factura:
    numero: str
    codigo_control: str


@dataclass(frozen=True)
class Mensaje:
    asunto: str
    cuerpo: str


@dataclass(frozen=True)
class ResultadoValidacion:
    valido: bool
    motivo: str
    boleto: Optional[Boleto] = None
