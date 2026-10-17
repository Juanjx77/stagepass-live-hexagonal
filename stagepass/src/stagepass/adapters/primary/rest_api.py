"""Adaptador primario COMPLETO: API REST sobre http.server (stdlib).

Traduce HTTP/JSON hacia los puertos primarios y los errores de dominio hacia códigos HTTP.
No contiene reglas de negocio."""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from stagepass.core.domain import excepciones as ex
from stagepass.core.domain.modelo import Asiento, Boleto, Evento, Orden
from stagepass.core.ports.entrada import ComandoIniciarCompra

_ESTATICOS = os.path.join(os.path.dirname(__file__), "static")

_CODIGOS_HTTP = [
    (ex.EventoNoEncontrado, 404), (ex.OrdenNoEncontrada, 404), (ex.BoletoNoEncontrado, 404),
    (ex.AsientoNoDisponible, 409), (ex.LimiteBoletosExcedido, 409), (ex.EventoNoDisponible, 409),
    (ex.TransicionOrdenInvalida, 409), (ex.ErrorPasarela, 502),
    (ex.SeleccionInvalida, 400), (ex.ClienteInvalido, 400), (ex.PasarelaDesconocida, 400),
    (ex.ErrorDominio, 400),
]


def _evento(e: Evento) -> dict:
    return {"id": e.id, "nombre": e.nombre, "tipo": e.tipo.value, "recinto_id": e.recinto_id,
            "fecha_hora": e.fecha_hora.isoformat(), "estado": e.estado.value}


def _asiento(a: Asiento) -> dict:
    return {"id": a.id, "codigo": a.codigo_ubicacion, "precio_base": str(a.precio_base),
            "estado": a.estado.value}


def _orden(o: Orden) -> dict:
    return {"id": o.id, "evento_id": o.evento_id, "cliente": o.cliente.nombre_completo,
            "asientos": [a.codigo_ubicacion for a in o.asientos],
            "tarifa_servicio": str(o.tarifa_servicio), "descuento": str(o.descuento),
            "monto_total": str(o.monto_total), "expira_en": o.expira_en.isoformat(),
            "estado": o.estado.value, "referencia_pago": o.referencia_pago,
            "numero_factura": o.numero_factura}


def _boleto(b: Boleto) -> dict:
    return {"id": b.id, "asiento_id": b.asiento_id, "codigo_redencion": b.codigo_redencion,
            "firma_hash": b.firma_hash, "fecha_emision": b.fecha_emision.isoformat()}


def crear_servidor(app, host: str = "127.0.0.1", puerto: int = 8000) -> ThreadingHTTPServer:
    """`app` expone los casos de uso (puertos primarios): catalogo, compra, pagos, ordenes, validacion."""

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silencia el log por petición
            pass

        # --- utilidades HTTP ---
        def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
            datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def _leer_json(self) -> dict:
            largo = int(self.headers.get("Content-Length") or 0)
            try:
                return json.loads(self.rfile.read(largo) or b"{}")
            except json.JSONDecodeError:
                raise ex.SeleccionInvalida("El cuerpo no es JSON válido")

        def _ejecutar(self, accion):
            try:
                codigo, cuerpo = accion()
                self._responder(codigo, cuerpo)
            except ex.ErrorDominio as error:
                codigo = next(c for tipo, c in _CODIGOS_HTTP if isinstance(error, tipo))
                self._responder(codigo, {"error": str(error), "tipo": type(error).__name__})
            except Exception:  # error técnico: no se filtran detalles internos
                self._responder(500, {"error": "Error interno"})

        # --- rutas ---
        def do_GET(self):
            ruta = urlparse(self.path).path
            if ruta in ("/", "/index.html"):
                with open(os.path.join(_ESTATICOS, "index.html"), "rb") as f:
                    return self._responder(200, f.read(), "text/html; charset=utf-8")
            if ruta == "/api/eventos":
                return self._ejecutar(lambda: (200, [_evento(e) for e in app.catalogo.listar_eventos()]))
            m = re.fullmatch(r"/api/eventos/([^/]+)/asientos", ruta)
            if m:
                return self._ejecutar(lambda: (200, [_asiento(a) for a in
                                                     app.catalogo.asientos_del_evento(m.group(1))]))
            m = re.fullmatch(r"/api/ordenes/([^/]+)", ruta)
            if m:
                def consultar():
                    o = app.ordenes.obtener_orden(m.group(1))
                    return 200, {**_orden(o), "boletos": [_boleto(b) for b in
                                                           app.ordenes.boletos_de_orden(o.id)]}
                return self._ejecutar(consultar)
            m = re.fullmatch(r"/api/boletos/([^/]+)/validacion", ruta)
            if m:
                def validar():
                    r = app.validacion.validar(m.group(1))
                    return 200, {"valido": r.valido, "motivo": r.motivo}
                return self._ejecutar(validar)
            self._responder(404, {"error": "Ruta no encontrada"})

        def do_POST(self):
            ruta = urlparse(self.path).path
            if ruta == "/api/compras":
                def comprar():
                    d, cli = self._leer_json(), None
                    cli = d.get("cliente") or {}
                    r = app.compra.iniciar_compra(ComandoIniciarCompra(
                        evento_id=d.get("evento_id", ""), asientos_ids=list(d.get("asientos", [])),
                        pasarela=d.get("pasarela", ""), nombre_completo=cli.get("nombre_completo", ""),
                        correo=cli.get("correo", ""), telefono_movil=cli.get("telefono_movil", ""),
                        nacionalidad=cli.get("nacionalidad", ""), cliente_id=cli.get("id")))
                    return 201, {"orden": _orden(r.orden), "url_pago": r.solicitud_pago.url_pago}
                return self._ejecutar(comprar)
            m = re.fullmatch(r"/webhooks/pagos/([^/]+)", ruta)
            if m:
                def webhook():
                    o = app.pagos.confirmar_pago(m.group(1), self._leer_json())
                    return 200, {"orden_id": o.id, "estado": o.estado.value}
                return self._ejecutar(webhook)
            self._responder(404, {"error": "Ruta no encontrada"})

    return ThreadingHTTPServer((host, puerto), Manejador)
