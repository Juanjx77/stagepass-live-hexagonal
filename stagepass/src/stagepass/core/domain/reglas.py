"""Reglas de negocio puras: tarifas dinámicas, disponibilidad de asientos y datos a firmar."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List

from .excepciones import SeleccionInvalida
from .modelo import Asiento, EstadoAsiento, Orden, ResultadoTarifa

MINUTOS_BLOQUEO = 10
MAX_BOLETOS_POR_CLIENTE_Y_EVENTO = 6
_CENTAVO = Decimal("0.01")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)


class CalculadoraTarifas:
    """Descuento por volumen y tarifa administrativa.

    1-2 boletos : tarifa 10 %, descuento 0 %
    3-5 boletos : tarifa  8 %, descuento 5 %
    más de 5    : tarifa  5 %, descuento 10 %
    La tarifa y el descuento se calculan sobre el valor base (suma de precios base).
    """

    def calcular(self, asientos: Iterable[Asiento]) -> ResultadoTarifa:
        asientos = list(asientos)
        cantidad = len(asientos)
        if cantidad == 0:
            raise SeleccionInvalida("Debe seleccionar al menos un asiento")
        if cantidad <= 2:
            pct_tarifa, pct_descuento = Decimal("0.10"), Decimal("0")
        elif cantidad <= 5:
            pct_tarifa, pct_descuento = Decimal("0.08"), Decimal("0.05")
        else:
            pct_tarifa, pct_descuento = Decimal("0.05"), Decimal("0.10")
        subtotal = sum((a.precio_base for a in asientos), Decimal("0"))
        tarifa = _redondear(subtotal * pct_tarifa)
        descuento = _redondear(subtotal * pct_descuento)
        return ResultadoTarifa(_redondear(subtotal), tarifa, descuento,
                               _redondear(subtotal + tarifa - descuento))


def instante_expiracion(ahora: datetime) -> datetime:
    return ahora + timedelta(minutes=MINUTOS_BLOQUEO)


def calcular_disponibilidad(asientos: Iterable[Asiento], ordenes: Iterable[Orden],
                            ahora: datetime) -> List[Asiento]:
    """Devuelve copias de los asientos con su estado real (el estado se deriva de las órdenes)."""
    vendidos, bloqueados = set(), set()
    for orden in ordenes:
        if orden.vende_asientos():
            vendidos.update(orden.asientos_ids())
        elif orden.bloquea_asientos(ahora):
            bloqueados.update(orden.asientos_ids())
    resultado = []
    for a in asientos:
        if a.id in vendidos:
            estado = EstadoAsiento.VENDIDO
        elif a.id in bloqueados:
            estado = EstadoAsiento.BLOQUEADO
        else:
            estado = EstadoAsiento.DISPONIBLE
        resultado.append(Asiento(a.id, a.recinto_id, a.codigo_ubicacion, a.precio_base, estado))
    return resultado


def boletos_activos(ordenes: Iterable[Orden], ahora: datetime) -> int:
    """Cantidad de boletas que un cliente ya tiene (aprobadas o en bloqueo vigente)."""
    return sum(len(o.asientos) for o in ordenes if o.vende_asientos() or o.bloquea_asientos(ahora))


def datos_para_firma(orden: Orden, asiento_id: str, codigo: str) -> str:
    """Datos inmutables de la orden que se firman al emitir y se recalculan al validar."""
    return "|".join([orden.id, orden.evento_id, orden.cliente.id, str(orden.monto_total),
                     asiento_id, codigo])
