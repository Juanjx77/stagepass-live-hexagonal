import unittest

from helpers import comando, nueva_app, wompi
from stagepass.core.domain.excepciones import (AsientoNoDisponible, EventoNoDisponible,
                                               LimiteBoletosExcedido, PasarelaDesconocida)
from stagepass.core.domain.modelo import EstadoAsiento, EstadoOrden

VIP = ["R1-VIP-A1", "R1-VIP-A2", "R1-VIP-A3"]


def estado_de(app, asiento_id, evento="E1"):
    return next(a.estado for a in app.catalogo.asientos_del_evento(evento) if a.id == asiento_id)


class TestCompra(unittest.TestCase):
    def setUp(self):
        self.app, self.reloj = nueva_app()

    def test_compra_bloquea_asientos_y_calcula_total(self):
        r = self.app.compra.iniciar_compra(comando(VIP[:3]))
        self.assertEqual(r.orden.estado, EstadoOrden.PENDIENTE_PAGO)
        self.assertEqual(str(r.orden.monto_total), "927000.00")  # 900000 + 8% - 5%
        self.assertEqual(estado_de(self.app, VIP[0]), EstadoAsiento.BLOQUEADO)
        self.assertTrue(r.solicitud_pago.url_pago.startswith("/simulador/wompi"))

    def test_asiento_bloqueado_no_se_puede_reservar_de_nuevo(self):
        self.app.compra.iniciar_compra(comando(VIP[:1]))
        with self.assertRaises(AsientoNoDisponible):
            self.app.compra.iniciar_compra(comando(VIP[:1], correo="otro@example.com"))

    def test_bloqueo_expira_a_los_10_minutos(self):
        self.app.compra.iniciar_compra(comando(VIP[:1]))
        self.reloj.avanzar(9)
        self.assertEqual(estado_de(self.app, VIP[0]), EstadoAsiento.BLOQUEADO)
        self.reloj.avanzar(1)
        self.assertEqual(estado_de(self.app, VIP[0]), EstadoAsiento.DISPONIBLE)
        self.app.compra.iniciar_compra(comando(VIP[:1], correo="otro@example.com"))  # ya se puede

    def test_liberador_marca_ordenes_expiradas(self):
        r = self.app.compra.iniciar_compra(comando(VIP[:2]))
        self.reloj.avanzar(11)
        self.assertEqual(self.app.liberacion.liberar_expirados(), 1)
        self.assertEqual(self.app.ordenes.obtener_orden(r.orden.id).estado, EstadoOrden.EXPIRADA)
        self.assertEqual(self.app.liberacion.liberar_expirados(), 0)

    def test_limite_de_seis_boletas_por_cliente_y_evento(self):
        gen = [f"R1-GEN-{i:02d}" for i in range(1, 8)]
        self.app.compra.iniciar_compra(comando(gen[:4]))
        with self.assertRaises(LimiteBoletosExcedido):
            self.app.compra.iniciar_compra(comando(gen[4:7]))
        self.app.compra.iniciar_compra(comando(gen[4:6]))  # 4 + 2 = 6 sí se permite

    def test_siete_asientos_en_una_compra_se_rechaza(self):
        with self.assertRaises(LimiteBoletosExcedido):
            self.app.compra.iniciar_compra(comando([f"R1-GEN-{i:02d}" for i in range(1, 8)]))

    def test_evento_cancelado_y_pasarela_desconocida(self):
        with self.assertRaises(EventoNoDisponible):
            self.app.compra.iniciar_compra(comando(["R2-PLA-01"], evento="E3"))
        with self.assertRaises(PasarelaDesconocida):
            self.app.compra.iniciar_compra(comando(VIP[:1], pasarela="bitcoin"))


class TestPago(unittest.TestCase):
    def setUp(self):
        self.app, self.reloj = nueva_app()
        self.orden = self.app.compra.iniciar_compra(comando(VIP[:2])).orden

    def test_pago_aprobado_emite_boletas_factura_y_notifica(self):
        o = self.app.pagos.confirmar_pago("wompi", wompi(self.orden.id))
        self.assertEqual(o.estado, EstadoOrden.APROBADA)
        self.assertTrue(o.numero_factura.startswith("SP-"))
        boletos = self.app.ordenes.boletos_de_orden(o.id)
        self.assertEqual(len(boletos), 2)
        self.assertEqual(estado_de(self.app, VIP[0]), EstadoAsiento.VENDIDO)
        for canal in self.app.notificadores:
            self.assertEqual(len(canal.bandeja), 1)

    def test_pago_rechazado_libera_asientos_y_no_emite(self):
        o = self.app.pagos.confirmar_pago("wompi", wompi(self.orden.id, "DECLINED"))
        self.assertEqual(o.estado, EstadoOrden.RECHAZADA)
        self.assertEqual(self.app.ordenes.boletos_de_orden(o.id), [])
        self.assertEqual(estado_de(self.app, VIP[0]), EstadoAsiento.DISPONIBLE)

    def test_pago_tardio_no_emite_boletas(self):
        self.reloj.avanzar(11)
        o = self.app.pagos.confirmar_pago("wompi", wompi(self.orden.id))
        self.assertEqual(o.estado, EstadoOrden.EXPIRADA)
        self.assertEqual(self.app.ordenes.boletos_de_orden(o.id), [])

    def test_confirmacion_repetida_es_idempotente(self):
        self.app.pagos.confirmar_pago("wompi", wompi(self.orden.id))
        self.app.pagos.confirmar_pago("wompi", wompi(self.orden.id))
        self.assertEqual(len(self.app.ordenes.boletos_de_orden(self.orden.id)), 2)

    def test_pago_pendiente_no_cambia_la_orden(self):
        o = self.app.pagos.confirmar_pago("wompi", wompi(self.orden.id, "PENDING"))
        self.assertEqual(o.estado, EstadoOrden.PENDIENTE_PAGO)

    def test_mismo_flujo_con_paypal_y_pse(self):
        for pasarela, correo, asiento, carga in [
            ("paypal", "p@example.com", "R1-GEN-01",
             lambda i: {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "x", "custom_id": i}}),
            ("pse", "q@example.com", "R1-GEN-02",
             lambda i: {"transactionState": "APPROVED", "referenceCode": i, "transactionId": "t"})]:
            orden = self.app.compra.iniciar_compra(comando([asiento], correo, pasarela)).orden
            self.assertEqual(self.app.pagos.confirmar_pago(pasarela, carga(orden.id)).estado,
                             EstadoOrden.APROBADA)


class TestValidacionBoletos(unittest.TestCase):
    def setUp(self):
        self.app, _ = nueva_app()
        orden = self.app.compra.iniciar_compra(comando(VIP[:1])).orden
        self.app.pagos.confirmar_pago("wompi", wompi(orden.id))
        self.boleto = self.app.ordenes.boletos_de_orden(orden.id)[0]

    def test_boleto_autentico(self):
        r = self.app.validacion.validar(self.boleto.codigo_redencion)
        self.assertTrue(r.valido)

    def test_firma_alterada_se_detecta(self):
        from dataclasses import replace
        repo = self.app.validacion._boletos
        repo.guardar_todos([replace(self.boleto, firma_hash="0" * 64)])
        self.assertFalse(self.app.validacion.validar(self.boleto.codigo_redencion).valido)


if __name__ == "__main__":
    unittest.main()
