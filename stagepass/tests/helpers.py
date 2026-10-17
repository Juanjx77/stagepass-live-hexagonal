from datetime import datetime, timedelta

from stagepass.config import aplicacion_en_memoria
from stagepass.core.ports.entrada import ComandoIniciarCompra
from stagepass.core.ports.salida import GeneradorIdentificadoresPuerto, RelojPuerto


class RelojFalso(RelojPuerto):
    def __init__(self):
        self.t = datetime(2027, 1, 1, 12, 0, 0)

    def ahora(self):
        return self.t

    def avanzar(self, minutos):
        self.t += timedelta(minutes=minutos)


class IdsSecuenciales(GeneradorIdentificadoresPuerto):
    def __init__(self):
        self.n = 0

    def nuevo_id(self):
        self.n += 1
        return f"id{self.n:03d}"


def nueva_app():
    reloj = RelojFalso()
    return aplicacion_en_memoria(reloj, IdsSecuenciales()), reloj


def comando(asientos, correo="ana@example.com", pasarela="wompi", evento="E1"):
    return ComandoIniciarCompra(evento, list(asientos), pasarela, "Ana Pérez", correo,
                                "3001234567", "Colombiana")


def wompi(orden_id, estado="APPROVED"):
    return {"event": "transaction.updated",
            "data": {"transaction": {"id": "W1", "status": estado, "reference": orden_id}}}
