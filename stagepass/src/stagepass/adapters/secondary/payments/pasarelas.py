"""Adaptadores SIMULADOS (mock) de pasarelas de pago: PayPal, Wompi y PSE.

Cada uno traduce el formato propio de su pasarela hacia el dominio (ConfirmacionPago) y
el dominio nunca ve esos DTOs. Los formatos de notificación son versiones simplificadas
e ilustrativas, no verificadas contra la API real de cada proveedor."""
from stagepass.core.domain.excepciones import ErrorPasarela
from stagepass.core.domain.modelo import ConfirmacionPago, EstadoPago, Orden, SolicitudPago
from stagepass.core.ports.salida import PasarelaPagoPuerto


class _PasarelaSimulada(PasarelaPagoPuerto):
    _NOMBRE = ""

    def nombre(self) -> str:
        return self._NOMBRE

    def registrar_pago(self, orden: Orden) -> SolicitudPago:
        if orden.monto_total <= 0:
            raise ErrorPasarela("Monto inválido para la pasarela")
        referencia = f"{self._NOMBRE.upper()}-{orden.id}"
        return SolicitudPago(referencia, f"/simulador/{self._NOMBRE}?ref={referencia}")

    @staticmethod
    def _exigir(valor, campo):
        if not valor:
            raise ErrorPasarela(f"Notificación inválida: falta '{campo}'")
        return valor


class PayPalSimulado(_PasarelaSimulada):
    _NOMBRE = "paypal"
    _ESTADOS = {"PAYMENT.CAPTURE.COMPLETED": EstadoPago.APROBADO,
                "PAYMENT.CAPTURE.DENIED": EstadoPago.RECHAZADO,
                "PAYMENT.CAPTURE.PENDING": EstadoPago.PENDIENTE}

    def interpretar_confirmacion(self, notificacion: dict) -> ConfirmacionPago:
        recurso = self._exigir(notificacion.get("resource"), "resource")
        estado = self._ESTADOS.get(notificacion.get("event_type"))
        if estado is None:
            raise ErrorPasarela("Evento de PayPal no reconocido")
        return ConfirmacionPago(self._exigir(recurso.get("custom_id"), "custom_id"), estado,
                                recurso.get("id", ""))


class WompiSimulado(_PasarelaSimulada):
    _NOMBRE = "wompi"
    _ESTADOS = {"APPROVED": EstadoPago.APROBADO, "DECLINED": EstadoPago.RECHAZADO,
                "ERROR": EstadoPago.RECHAZADO, "VOIDED": EstadoPago.RECHAZADO,
                "PENDING": EstadoPago.PENDIENTE}

    def interpretar_confirmacion(self, notificacion: dict) -> ConfirmacionPago:
        datos = self._exigir(notificacion.get("data"), "data")
        tx = self._exigir(datos.get("transaction"), "transaction")
        estado = self._ESTADOS.get(tx.get("status"))
        if estado is None:
            raise ErrorPasarela("Estado de Wompi no reconocido")
        return ConfirmacionPago(self._exigir(tx.get("reference"), "reference"), estado,
                                tx.get("id", ""))


class PseSimulado(_PasarelaSimulada):
    _NOMBRE = "pse"
    _ESTADOS = {"APPROVED": EstadoPago.APROBADO, "REJECTED": EstadoPago.RECHAZADO,
                "FAILED": EstadoPago.RECHAZADO, "PENDING": EstadoPago.PENDIENTE}

    def interpretar_confirmacion(self, notificacion: dict) -> ConfirmacionPago:
        estado = self._ESTADOS.get(notificacion.get("transactionState"))
        if estado is None:
            raise ErrorPasarela("Estado de PSE no reconocido")
        return ConfirmacionPago(self._exigir(notificacion.get("referenceCode"), "referenceCode"),
                                estado, notificacion.get("transactionId", ""))
