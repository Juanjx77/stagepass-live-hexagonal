"""Adaptador COMPLETO de credenciales criptográficas: código de redención y firma HMAC-SHA256.

La clave secreta de cada evento se deriva de una clave maestra: HMAC(maestra, evento_id).
Así el dominio nunca conoce ni transporta secretos."""
import hashlib
import hmac
import secrets

from stagepass.core.domain.modelo import Boleto
from stagepass.core.ports.salida import GeneradorCredencialesPuerto

_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin caracteres ambiguos (0/O, 1/I)


class HmacCredenciales(GeneradorCredencialesPuerto):
    def __init__(self, clave_maestra: bytes):
        if len(clave_maestra) < 16:
            raise ValueError("La clave maestra debe tener al menos 16 bytes")
        self._maestra = clave_maestra

    def generar_codigo_redencion(self) -> str:
        grupos = ["".join(secrets.choice(_ALFABETO) for _ in range(4)) for _ in range(3)]
        return "-".join(grupos)

    def firmar(self, evento_id: str, datos: str) -> str:
        return hmac.new(self._clave_evento(evento_id), datos.encode("utf-8"),
                        hashlib.sha256).hexdigest()

    def verificar(self, evento_id: str, datos: str, firma: str) -> bool:
        return hmac.compare_digest(self.firmar(evento_id, datos), firma)

    def representacion_grafica(self, boleto: Boleto) -> str:
        """Texto que se codificaría en el QR del boleto. Dibujar la imagen es responsabilidad
        de un adaptador con librería QR; aquí se entrega el contenido ya firmado."""
        return f"stagepass://boleto?c={boleto.codigo_redencion}&f={boleto.firma_hash[:16]}"

    def _clave_evento(self, evento_id: str) -> bytes:
        return hmac.new(self._maestra, evento_id.encode("utf-8"), hashlib.sha256).digest()
