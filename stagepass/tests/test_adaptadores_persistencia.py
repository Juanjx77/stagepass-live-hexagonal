import sqlite3
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from stagepass.adapters.secondary.persistence.mongo import MongoBoletoRepositorio, MongoOrdenRepositorio
from stagepass.adapters.secondary.persistence.mysql import MySqlEventoRepositorio, MySqlRecintoRepositorio
from stagepass.core.domain.modelo import (Asiento, Boleto, Cliente, EstadoEvento, EstadoOrden, Orden,
                                          TipoEvento)

try:
    import mongomock
except ImportError:  # pragma: no cover
    mongomock = None


def orden_ejemplo(oid="o1", cliente="ana@example.com", estado=EstadoOrden.PENDIENTE_PAGO,
                  expira=datetime(2027, 1, 1, 12, 10)):
    return Orden(oid, "E1", Cliente(cliente, "Ana", cliente, "300", "CO"),
                 [Asiento("a1", "R1", "VIP-A1", Decimal("300000.00"))],
                 Decimal("30000.00"), Decimal("0.00"), Decimal("330000.00"), expira, estado)


@unittest.skipIf(mongomock is None, "mongomock no instalado")
class TestMongo(unittest.TestCase):
    def setUp(self):
        base = mongomock.MongoClient()["t"]
        self.ordenes = MongoOrdenRepositorio(base["ordenes"])
        self.boletos = MongoBoletoRepositorio(base["boletos"])

    def test_ida_y_vuelta_de_una_orden(self):
        o = orden_ejemplo()
        self.ordenes.guardar(o)
        leida = self.ordenes.obtener("o1")
        self.assertEqual(leida.monto_total, Decimal("330000.00"))
        self.assertEqual(leida.cliente, o.cliente)
        self.assertEqual(leida.asientos[0].codigo_ubicacion, "VIP-A1")
        self.assertIsNone(self.ordenes.obtener("nope"))

    def test_guardar_dos_veces_actualiza(self):
        o = orden_ejemplo()
        self.ordenes.guardar(o)
        o.aprobar("REF")
        self.ordenes.guardar(o)
        self.assertEqual(self.ordenes.obtener("o1").estado, EstadoOrden.APROBADA)

    def test_consultas(self):
        self.ordenes.guardar(orden_ejemplo("o1"))
        self.ordenes.guardar(orden_ejemplo("o2", "otro@example.com"))
        self.assertEqual(len(self.ordenes.listar_por_evento("E1")), 2)
        self.assertEqual(len(self.ordenes.listar_por_cliente_y_evento("ana@example.com", "E1")), 1)
        antes, despues = datetime(2027, 1, 1, 12, 5), datetime(2027, 1, 1, 12, 15)
        self.assertEqual(self.ordenes.listar_pendientes_expiradas(antes), [])
        self.assertEqual(len(self.ordenes.listar_pendientes_expiradas(despues)), 2)

    def test_boletos(self):
        b = Boleto("b1", "o1", "E1", "a1", "AAAA-BBBB-CCCC", "f" * 64, datetime(2027, 1, 1))
        self.boletos.guardar_todos([b])
        self.assertEqual(self.boletos.obtener_por_codigo("AAAA-BBBB-CCCC"), b)
        self.assertEqual(self.boletos.listar_por_orden("o1"), [b])
        self.assertIsNone(self.boletos.obtener_por_codigo("X"))


class TestMySqlLegacy(unittest.TestCase):
    """Se prueba el mapeo y las consultas con SQLite (mismo esquema, marcador '?')."""

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript("""
            CREATE TABLE recintos (id TEXT PRIMARY KEY, nombre TEXT, aforo INT);
            CREATE TABLE asientos (id TEXT PRIMARY KEY, recinto_id TEXT, codigo_ubicacion TEXT, precio_base NUM);
            CREATE TABLE eventos (id TEXT PRIMARY KEY, nombre TEXT, tipo TEXT, recinto_id TEXT, fecha_hora TEXT, estado TEXT);
            INSERT INTO recintos VALUES ('R1','Arena',2);
            INSERT INTO asientos VALUES ('s1','R1','VIP-A1',300000.00),('s2','R1','General-01',80000.00);
            INSERT INTO eventos VALUES ('E1','Rock','FESTIVAL','R1','2027-03-20 19:00:00','PROGRAMADO');
        """)
        fabrica = lambda: _NoCierra(self.con)
        self.eventos = MySqlEventoRepositorio(fabrica, "?")
        self.recintos = MySqlRecintoRepositorio(fabrica, "?")

    def test_evento(self):
        e = self.eventos.obtener("E1")
        self.assertEqual((e.tipo, e.estado), (TipoEvento.FESTIVAL, EstadoEvento.PROGRAMADO))
        self.assertEqual(e.fecha_hora, datetime(2027, 3, 20, 19, 0))
        self.assertIsNone(self.eventos.obtener("zz"))
        self.assertEqual(len(self.eventos.listar()), 1)

    def test_recinto_y_asientos(self):
        self.assertEqual(self.recintos.obtener_aforo("R1"), 2)
        self.assertEqual(self.recintos.obtener_aforo("nope"), 0)
        asientos = self.recintos.listar_asientos("R1")
        self.assertEqual([a.codigo_ubicacion for a in asientos], ["General-01", "VIP-A1"])
        self.assertEqual(asientos[1].precio_base, Decimal("300000.0"))


class _NoCierra:
    """Envuelve la conexión SQLite para que close() no la destruya entre consultas."""
    def __init__(self, con):
        self._con = con

    def cursor(self):
        return self._con.cursor()

    def close(self):
        pass


if __name__ == "__main__":
    unittest.main()
