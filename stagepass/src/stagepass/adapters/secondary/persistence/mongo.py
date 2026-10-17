"""Adaptadores COMPLETOS de MongoDB para órdenes y boletas (patrón Repository).

Reciben la colección ya construida (inyección por constructor), de modo que el dominio no
conoce pymongo y los mismos adaptadores se prueban con una colección simulada (mongomock)."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from stagepass.core.domain.modelo import (Asiento, Boleto, Cliente, EstadoAsiento, EstadoOrden,
                                          Orden)
from stagepass.core.ports.salida import BoletoRepositorio, OrdenRepositorio


def _orden_a_doc(o: Orden) -> dict:
    return {
        "_id": o.id, "evento_id": o.evento_id,
        "cliente": {"id": o.cliente.id, "nombre_completo": o.cliente.nombre_completo,
                    "correo": o.cliente.correo, "telefono_movil": o.cliente.telefono_movil,
                    "nacionalidad": o.cliente.nacionalidad},
        "asientos": [{"id": a.id, "recinto_id": a.recinto_id, "codigo_ubicacion": a.codigo_ubicacion,
                      "precio_base": str(a.precio_base)} for a in o.asientos],
        "tarifa_servicio": str(o.tarifa_servicio), "descuento": str(o.descuento),
        "monto_total": str(o.monto_total), "expira_en": o.expira_en, "estado": o.estado.value,
        "referencia_pago": o.referencia_pago, "numero_factura": o.numero_factura,
    }


def _doc_a_orden(d: dict) -> Orden:
    c = d["cliente"]
    return Orden(
        id=d["_id"], evento_id=d["evento_id"],
        cliente=Cliente(c["id"], c["nombre_completo"], c["correo"], c["telefono_movil"], c["nacionalidad"]),
        asientos=[Asiento(a["id"], a["recinto_id"], a["codigo_ubicacion"], Decimal(a["precio_base"]),
                          EstadoAsiento.BLOQUEADO) for a in d["asientos"]],
        tarifa_servicio=Decimal(d["tarifa_servicio"]), descuento=Decimal(d["descuento"]),
        monto_total=Decimal(d["monto_total"]), expira_en=d["expira_en"],
        estado=EstadoOrden(d["estado"]), referencia_pago=d.get("referencia_pago"),
        numero_factura=d.get("numero_factura"))


class MongoOrdenRepositorio(OrdenRepositorio):
    def __init__(self, coleccion):
        self._col = coleccion

    def guardar(self, orden: Orden) -> None:
        self._col.replace_one({"_id": orden.id}, _orden_a_doc(orden), upsert=True)

    def obtener(self, orden_id: str) -> Optional[Orden]:
        d = self._col.find_one({"_id": orden_id})
        return _doc_a_orden(d) if d else None

    def listar_por_evento(self, evento_id: str) -> List[Orden]:
        return [_doc_a_orden(d) for d in self._col.find({"evento_id": evento_id})]

    def listar_por_cliente_y_evento(self, cliente_id: str, evento_id: str) -> List[Orden]:
        return [_doc_a_orden(d) for d in
                self._col.find({"evento_id": evento_id, "cliente.id": cliente_id})]

    def listar_pendientes_expiradas(self, ahora: datetime) -> List[Orden]:
        filtro = {"estado": EstadoOrden.PENDIENTE_PAGO.value, "expira_en": {"$lte": ahora}}
        return [_doc_a_orden(d) for d in self._col.find(filtro)]


class MongoBoletoRepositorio(BoletoRepositorio):
    def __init__(self, coleccion):
        self._col = coleccion

    def guardar_todos(self, boletos: List[Boleto]) -> None:
        for b in boletos:
            self._col.replace_one({"_id": b.id}, {
                "_id": b.id, "orden_id": b.orden_id, "evento_id": b.evento_id,
                "asiento_id": b.asiento_id, "codigo_redencion": b.codigo_redencion,
                "firma_hash": b.firma_hash, "fecha_emision": b.fecha_emision}, upsert=True)

    def listar_por_orden(self, orden_id: str) -> List[Boleto]:
        return [self._a_boleto(d) for d in self._col.find({"orden_id": orden_id})]

    def obtener_por_codigo(self, codigo_redencion: str) -> Optional[Boleto]:
        d = self._col.find_one({"codigo_redencion": codigo_redencion})
        return self._a_boleto(d) if d else None

    @staticmethod
    def _a_boleto(d: dict) -> Boleto:
        return Boleto(d["_id"], d["orden_id"], d["evento_id"], d["asiento_id"],
                      d["codigo_redencion"], d["firma_hash"], d["fecha_emision"])
