"""Raíz de composición: único lugar donde se eligen adaptadores y se inyectan en los casos de uso."""
import os
from dataclasses import dataclass, field
from typing import List

from stagepass.adapters.secondary.billing.dian import DianSimulado
from stagepass.adapters.secondary.crypto.hmac_credenciales import HmacCredenciales
from stagepass.adapters.secondary.notifications.canales import (SendgridCorreoSimulado,
                                                                 WhatsAppSimulado)
from stagepass.adapters.secondary.payments.pasarelas import (PayPalSimulado, PseSimulado,
                                                              WompiSimulado)
from stagepass.adapters.secondary.persistence.memoria import (BoletoRepositorioMemoria,
                                                              EventoRepositorioMemoria,
                                                              OrdenRepositorioMemoria,
                                                              RecintoRepositorioMemoria, datos_demo)
from stagepass.adapters.secondary.system.sistema import GeneradorUuid, RelojSistema
from stagepass.core.application.servicios import (ServicioCatalogo, ServicioCompra,
                                                  ServicioConsultaOrdenes, ServicioLiberacionBloqueos,
                                                  ServicioPagos, ServicioValidacionBoletos)


@dataclass
class Aplicacion:
    catalogo: ServicioCatalogo
    compra: ServicioCompra
    pagos: ServicioPagos
    ordenes: ServicioConsultaOrdenes
    validacion: ServicioValidacionBoletos
    liberacion: ServicioLiberacionBloqueos
    notificadores: List = field(default_factory=list)


def construir_aplicacion(eventos, recintos, ordenes, boletos, reloj=None, ids=None,
                         clave_maestra: bytes = b"cambia-esta-clave-en-produccion") -> Aplicacion:
    """Ensambla la aplicación con los puertos secundarios que reciba (inyección por constructor)."""
    reloj, ids = reloj or RelojSistema(), ids or GeneradorUuid()
    pasarelas = {p.nombre(): p for p in (PayPalSimulado(), WompiSimulado(), PseSimulado())}
    notificadores = [SendgridCorreoSimulado(), WhatsAppSimulado()]
    credenciales = HmacCredenciales(clave_maestra)
    return Aplicacion(
        catalogo=ServicioCatalogo(eventos, recintos, ordenes, reloj),
        compra=ServicioCompra(eventos, recintos, ordenes, pasarelas, reloj, ids),
        pagos=ServicioPagos(ordenes, boletos, pasarelas, credenciales, DianSimulado(),
                            notificadores, reloj, ids),
        ordenes=ServicioConsultaOrdenes(ordenes, boletos),
        validacion=ServicioValidacionBoletos(ordenes, boletos, credenciales),
        liberacion=ServicioLiberacionBloqueos(ordenes, reloj),
        notificadores=notificadores)


def aplicacion_en_memoria(reloj=None, ids=None) -> Aplicacion:
    eventos, asientos = datos_demo()
    return construir_aplicacion(EventoRepositorioMemoria(eventos), RecintoRepositorioMemoria(asientos),
                                OrdenRepositorioMemoria(), BoletoRepositorioMemoria(), reloj, ids)


def aplicacion_real() -> Aplicacion:
    """MySQL legacy (consulta) + MongoDB (órdenes y boletas). Requiere los drivers y variables:
    MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, MONGO_URI, MONGO_DB, STAGEPASS_CLAVE."""
    import mysql.connector  # noqa: WPS433 (solo se importa en modo real)
    from pymongo import MongoClient

    from stagepass.adapters.secondary.persistence.mongo import (MongoBoletoRepositorio,
                                                                MongoOrdenRepositorio)
    from stagepass.adapters.secondary.persistence.mysql import (MySqlEventoRepositorio,
                                                                MySqlRecintoRepositorio)

    def conexion():
        return mysql.connector.connect(host=os.environ["MYSQL_HOST"], user=os.environ["MYSQL_USER"],
                                       password=os.environ["MYSQL_PASSWORD"], database=os.environ["MYSQL_DB"])

    base = MongoClient(os.environ["MONGO_URI"])[os.environ.get("MONGO_DB", "stagepass")]
    return construir_aplicacion(MySqlEventoRepositorio(conexion), MySqlRecintoRepositorio(conexion),
                                MongoOrdenRepositorio(base["ordenes"]),
                                MongoBoletoRepositorio(base["boletos"]),
                                clave_maestra=os.environ["STAGEPASS_CLAVE"].encode())
