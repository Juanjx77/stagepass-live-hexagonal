"""Adaptadores en MEMORIA (mock): para pruebas aisladas y para ejecutar la demo sin bases de datos."""
import copy
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from stagepass.core.domain.modelo import (Asiento, Boleto, EstadoEvento, EstadoOrden, Evento,
                                          Orden, TipoEvento)
from stagepass.core.ports.salida import (BoletoRepositorio, EventoRepositorio, OrdenRepositorio,
                                         RecintoRepositorio)


class EventoRepositorioMemoria(EventoRepositorio):
    def __init__(self, eventos: List[Evento]):
        self._eventos = {e.id: e for e in eventos}

    def obtener(self, evento_id: str) -> Optional[Evento]:
        return self._eventos.get(evento_id)

    def listar(self) -> List[Evento]:
        return list(self._eventos.values())


class RecintoRepositorioMemoria(RecintoRepositorio):
    def __init__(self, asientos_por_recinto: Dict[str, List[Asiento]]):
        self._asientos = asientos_por_recinto

    def obtener_aforo(self, recinto_id: str) -> int:
        return len(self._asientos.get(recinto_id, []))

    def listar_asientos(self, recinto_id: str) -> List[Asiento]:
        return [copy.copy(a) for a in self._asientos.get(recinto_id, [])]


class OrdenRepositorioMemoria(OrdenRepositorio):
    def __init__(self):
        self._ordenes: Dict[str, Orden] = {}

    def guardar(self, orden: Orden) -> None:
        self._ordenes[orden.id] = copy.deepcopy(orden)  # simula persistencia: no comparte referencias

    def obtener(self, orden_id: str) -> Optional[Orden]:
        o = self._ordenes.get(orden_id)
        return copy.deepcopy(o) if o else None

    def listar_por_evento(self, evento_id: str) -> List[Orden]:
        return [copy.deepcopy(o) for o in self._ordenes.values() if o.evento_id == evento_id]

    def listar_por_cliente_y_evento(self, cliente_id: str, evento_id: str) -> List[Orden]:
        return [copy.deepcopy(o) for o in self._ordenes.values()
                if o.evento_id == evento_id and o.cliente.id == cliente_id]

    def listar_pendientes_expiradas(self, ahora: datetime) -> List[Orden]:
        return [copy.deepcopy(o) for o in self._ordenes.values() if o.esta_expirada(ahora)]


class BoletoRepositorioMemoria(BoletoRepositorio):
    def __init__(self):
        self._boletos: Dict[str, Boleto] = {}

    def guardar_todos(self, boletos: List[Boleto]) -> None:
        for b in boletos:
            self._boletos[b.id] = b

    def listar_por_orden(self, orden_id: str) -> List[Boleto]:
        return [b for b in self._boletos.values() if b.orden_id == orden_id]

    def obtener_por_codigo(self, codigo_redencion: str) -> Optional[Boleto]:
        return next((b for b in self._boletos.values() if b.codigo_redencion == codigo_redencion), None)


def datos_demo():
    """Catálogo de ejemplo equivalente al que viviría en el MySQL legacy."""
    asientos = {
        "R1": [Asiento(f"R1-VIP-A{i}", "R1", f"VIP-A{i}", Decimal("300000")) for i in range(1, 11)]
              + [Asiento(f"R1-GEN-{i:02d}", "R1", f"General-{i:02d}", Decimal("80000")) for i in range(1, 31)],
        "R2": [Asiento(f"R2-PLA-{i:02d}", "R2", f"Platea-{i:02d}", Decimal("120000")) for i in range(1, 21)],
    }
    eventos = [
        Evento("E1", "Festival Andino de Rock", TipoEvento.FESTIVAL, "R1",
               datetime(2027, 3, 20, 19, 0), EstadoEvento.PROGRAMADO),
        Evento("E2", "Obra: La Casa de Bernarda Alba", TipoEvento.TEATRO, "R2",
               datetime(2027, 4, 2, 20, 0), EstadoEvento.PROGRAMADO),
        Evento("E3", "Concierto cancelado de prueba", TipoEvento.CONCIERTO, "R2",
               datetime(2027, 5, 1, 21, 0), EstadoEvento.CANCELADO),
    ]
    return eventos, asientos
