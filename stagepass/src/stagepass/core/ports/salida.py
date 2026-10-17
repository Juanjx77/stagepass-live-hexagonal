"""Puertos secundarios (driven): lo que el núcleo necesita del exterior para operar.
Los define el dominio; la infraestructura los implementa (inversión de dependencias)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from ..domain.modelo import (Asiento, Boleto, Cliente, ConfirmacionPago, Evento, Factura,
                             Mensaje, Orden, SolicitudPago)


# ---- Persistencia dual -------------------------------------------------------------------
# Legacy (MySQL): consulta de recintos, aforos, asientos y eventos
class EventoRepositorio(ABC):
    @abstractmethod
    def obtener(self, evento_id: str) -> Optional[Evento]: ...

    @abstractmethod
    def listar(self) -> List[Evento]: ...


class RecintoRepositorio(ABC):
    @abstractmethod
    def obtener_aforo(self, recinto_id: str) -> int: ...

    @abstractmethod
    def listar_asientos(self, recinto_id: str) -> List[Asiento]: ...


# Nueva base (MongoDB): órdenes y boletas emitidas
class OrdenRepositorio(ABC):
    @abstractmethod
    def guardar(self, orden: Orden) -> None: ...

    @abstractmethod
    def obtener(self, orden_id: str) -> Optional[Orden]: ...

    @abstractmethod
    def listar_por_evento(self, evento_id: str) -> List[Orden]: ...

    @abstractmethod
    def listar_por_cliente_y_evento(self, cliente_id: str, evento_id: str) -> List[Orden]: ...

    @abstractmethod
    def listar_pendientes_expiradas(self, ahora: datetime) -> List[Orden]: ...


class BoletoRepositorio(ABC):
    @abstractmethod
    def guardar_todos(self, boletos: List[Boleto]) -> None: ...

    @abstractmethod
    def listar_por_orden(self, orden_id: str) -> List[Boleto]: ...

    @abstractmethod
    def obtener_por_codigo(self, codigo_redencion: str) -> Optional[Boleto]: ...


# ---- Pasarelas de pago homogéneas ----------------------------------------------------------
class PasarelaPagoPuerto(ABC):
    """Puerto común: registro de pagos y recepción de confirmación, sin DTOs de ninguna pasarela."""

    @abstractmethod
    def nombre(self) -> str: ...

    @abstractmethod
    def registrar_pago(self, orden: Orden) -> SolicitudPago: ...

    @abstractmethod
    def interpretar_confirmacion(self, notificacion: dict) -> ConfirmacionPago: ...


# ---- Servicios externos complementarios -----------------------------------------------------
class GeneradorCredencialesPuerto(ABC):
    @abstractmethod
    def generar_codigo_redencion(self) -> str: ...

    @abstractmethod
    def firmar(self, evento_id: str, datos: str) -> str: ...

    @abstractmethod
    def verificar(self, evento_id: str, datos: str, firma: str) -> bool: ...

    @abstractmethod
    def representacion_grafica(self, boleto: Boleto) -> str: ...


class NotificacionPuerto(ABC):
    @abstractmethod
    def canal(self) -> str: ...

    @abstractmethod
    def enviar(self, destinatario: Cliente, mensaje: Mensaje) -> None: ...


class FacturacionElectronicaPuerto(ABC):
    @abstractmethod
    def emitir_factura(self, orden: Orden) -> Factura: ...


# ---- Utilidades que el negocio necesita y no debe resolver por su cuenta ----------------------
class RelojPuerto(ABC):
    @abstractmethod
    def ahora(self) -> datetime: ...


class GeneradorIdentificadoresPuerto(ABC):
    @abstractmethod
    def nuevo_id(self) -> str: ...
