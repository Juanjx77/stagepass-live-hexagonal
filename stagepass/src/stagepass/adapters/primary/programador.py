"""Adaptador primario COMPLETO: temporizador que dispara la liberación de bloqueos vencidos."""
import logging
import threading

from stagepass.core.ports.entrada import LiberarBloqueosExpiradosUseCase

log = logging.getLogger("stagepass.programador")


class ProgramadorLiberacion:
    def __init__(self, caso_uso: LiberarBloqueosExpiradosUseCase, intervalo_segundos: float = 30.0):
        self._caso_uso, self._intervalo = caso_uso, intervalo_segundos
        self._detener = threading.Event()
        self._hilo = threading.Thread(target=self._ciclo, daemon=True)

    def iniciar(self) -> None:
        self._hilo.start()

    def detener(self) -> None:
        self._detener.set()

    def _ciclo(self) -> None:
        while not self._detener.wait(self._intervalo):
            try:
                liberadas = self._caso_uso.liberar_expirados()
                if liberadas:
                    log.info("Órdenes expiradas liberadas: %s", liberadas)
            except Exception:  # el temporizador nunca debe morir por un error puntual
                log.exception("Fallo al liberar bloqueos")
