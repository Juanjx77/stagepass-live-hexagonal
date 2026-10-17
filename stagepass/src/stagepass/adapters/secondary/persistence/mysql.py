"""Adaptadores de consulta al MySQL LEGACY (eventos, recintos, aforos y asientos).

Usan una función que entrega una conexión DB-API (en producción, mysql.connector.connect).
`marcador` es el placeholder del driver: '%s' en MySQL; en las pruebas se usa SQLite con '?'.
Son de solo lectura: el sistema legacy no se modifica."""
from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Optional

from stagepass.core.domain.modelo import Asiento, EstadoEvento, Evento, TipoEvento
from stagepass.core.ports.salida import EventoRepositorio, RecintoRepositorio


def _a_datetime(valor) -> datetime:
    return valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor))


class MySqlEventoRepositorio(EventoRepositorio):
    _COLS = "id, nombre, tipo, recinto_id, fecha_hora, estado"

    def __init__(self, conexion: Callable, marcador: str = "%s"):
        self._conexion, self._m = conexion, marcador

    def obtener(self, evento_id: str) -> Optional[Evento]:
        filas = self._consultar(f"SELECT {self._COLS} FROM eventos WHERE id = {self._m}", (evento_id,))
        return self._a_evento(filas[0]) if filas else None

    def listar(self) -> List[Evento]:
        return [self._a_evento(f) for f in
                self._consultar(f"SELECT {self._COLS} FROM eventos ORDER BY fecha_hora", ())]

    def _consultar(self, sql, params):
        con = self._conexion()
        try:
            cur = con.cursor()
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            con.close()

    @staticmethod
    def _a_evento(f) -> Evento:
        return Evento(str(f[0]), f[1], TipoEvento(f[2]), str(f[3]), _a_datetime(f[4]),
                      EstadoEvento(f[5]))


class MySqlRecintoRepositorio(RecintoRepositorio):
    def __init__(self, conexion: Callable, marcador: str = "%s"):
        self._conexion, self._m = conexion, marcador

    def obtener_aforo(self, recinto_id: str) -> int:
        con = self._conexion()
        try:
            cur = con.cursor()
            cur.execute(f"SELECT aforo FROM recintos WHERE id = {self._m}", (recinto_id,))
            fila = cur.fetchone()
            return int(fila[0]) if fila else 0
        finally:
            con.close()

    def listar_asientos(self, recinto_id: str) -> List[Asiento]:
        con = self._conexion()
        try:
            cur = con.cursor()
            cur.execute("SELECT id, recinto_id, codigo_ubicacion, precio_base FROM asientos "
                        f"WHERE recinto_id = {self._m} ORDER BY codigo_ubicacion", (recinto_id,))
            return [Asiento(str(f[0]), str(f[1]), f[2], Decimal(str(f[3]))) for f in cur.fetchall()]
        finally:
            con.close()
