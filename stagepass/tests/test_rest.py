import json
import threading
import unittest
import urllib.error
import urllib.request

from helpers import nueva_app
from stagepass.adapters.primary.rest_api import crear_servidor


class TestRest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.reloj = nueva_app()
        cls.servidor = crear_servidor(cls.app, "127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def llamar(self, metodo, ruta, cuerpo=None):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(self.base + ruta, data=datos, method=metodo,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def compra(self, asientos, correo="rest@example.com"):
        return self.llamar("POST", "/api/compras", {
            "evento_id": "E2", "asientos": asientos, "pasarela": "pse",
            "cliente": {"nombre_completo": "Luis Gómez", "correo": correo,
                        "telefono_movil": "3110000000", "nacionalidad": "Colombiana"}})

    def test_flujo_completo_de_compra_por_http(self):
        codigo, eventos = self.llamar("GET", "/api/eventos")
        self.assertEqual(codigo, 200)
        self.assertEqual(len(eventos), 3)

        codigo, cuerpo = self.compra(["R2-PLA-01", "R2-PLA-02"])
        self.assertEqual(codigo, 201)
        orden_id = cuerpo["orden"]["id"]
        self.assertEqual(cuerpo["orden"]["monto_total"], "264000.00")

        codigo, cuerpo = self.llamar("POST", "/webhooks/pagos/pse", {
            "transactionState": "APPROVED", "referenceCode": orden_id, "transactionId": "T1"})
        self.assertEqual((codigo, cuerpo["estado"]), (200, "APROBADA"))

        codigo, orden = self.llamar("GET", f"/api/ordenes/{orden_id}")
        self.assertEqual(len(orden["boletos"]), 2)
        codigo_boleto = orden["boletos"][0]["codigo_redencion"]
        codigo, v = self.llamar("GET", f"/api/boletos/{codigo_boleto}/validacion")
        self.assertTrue(v["valido"])

    def test_errores_de_dominio_se_traducen_a_codigos_http(self):
        self.assertEqual(self.compra(["R2-PLA-10"], "a@example.com")[0], 201)
        codigo, cuerpo = self.compra(["R2-PLA-10"], "b@example.com")
        self.assertEqual((codigo, cuerpo["tipo"]), (409, "AsientoNoDisponible"))
        self.assertEqual(self.compra([], "c@example.com")[0], 400)
        self.assertEqual(self.llamar("GET", "/api/ordenes/no-existe")[0], 404)
        self.assertEqual(self.llamar("GET", "/api/eventos/ZZ/asientos")[0], 404)
        self.assertEqual(self.llamar("POST", "/webhooks/pagos/pse", {"transactionState": "???"})[0], 502)

    def test_pagina_principal(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn(b"StagePass Live", r.read())


if __name__ == "__main__":
    unittest.main()
