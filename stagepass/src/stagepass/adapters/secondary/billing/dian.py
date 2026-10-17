"""Adaptador SIMULADO de facturación electrónica (DIAN). No se conecta a ninguna autoridad real."""
import hashlib

from stagepass.core.domain.modelo import Factura, Orden
from stagepass.core.ports.salida import FacturacionElectronicaPuerto


class DianSimulado(FacturacionElectronicaPuerto):
    def emitir_factura(self, orden: Orden) -> Factura:
        control = hashlib.sha384(f"{orden.id}|{orden.monto_total}".encode()).hexdigest()
        return Factura(f"SP-{orden.id.upper()}", control)
