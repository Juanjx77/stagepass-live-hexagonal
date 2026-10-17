# StagePass Live — Arquitectura Hexagonal (Taller UNAB)

Plataforma web de venta y expedición de boletería digital, construida con **Arquitectura Hexagonal**
(Puertos y Adaptadores). Python 3.10+; el núcleo y el modo demo usan solo la biblioteca estándar.

## Estructura

```
src/stagepass/
  core/                         <- INSIDE: no importa nada de infraestructura
    domain/   modelo.py  reglas.py  excepciones.py
    ports/    entrada.py (puertos primarios)   salida.py (puertos secundarios)
    application/ servicios.py   (casos de uso: implementan entrada, usan salida)
  adapters/                     <- OUTSIDE
    primary/   rest_api.py  programador.py  static/index.html
    secondary/ persistence/{memoria,mongo,mysql}.py  payments/pasarelas.py
               crypto/hmac_credenciales.py  notifications/canales.py  billing/dian.py  system/sistema.py
  config.py                     <- raíz de composición (inyección de dependencias por constructor)
  main.py
tests/    docs/ (diagramas UML)    tools/generar_uml.py    legacy_mysql.sql
```

## Cómo ejecutarlo

```bash
# Demo sin bases de datos (repositorios en memoria):
PYTHONPATH=src python -m stagepass.main            # abre http://localhost:8000

# Pruebas (32):
pip install mongomock                              # solo para la prueba del adaptador MongoDB
PYTHONPATH=src:tests python -m unittest discover -s tests -v

# Modo real (MySQL legacy + MongoDB):
pip install -r requirements.txt
export MYSQL_HOST=... MYSQL_USER=... MYSQL_PASSWORD=... MYSQL_DB=... MONGO_URI=... STAGEPASS_CLAVE=...
PYTHONPATH=src python -m stagepass.main --real

# Regenerar los diagramas UML desde el código (requiere Graphviz):
python tools/generar_uml.py       # PNG/SVG + uml_completo.mmd
python tools/generar_drawio.py    # docs/StagePass_UML.drawio (3 páginas, editable en draw.io)
```

En la página web: elige evento, selecciona asientos, llena tus datos, inicia la compra y usa los botones
"Simular pago aprobado/rechazado" (equivalen a la notificación asíncrona de la pasarela).

## Cómo se cumple cada requisito del taller

| Requisito | Dónde / cómo |
|---|---|
| Soberanía del núcleo | `core/` solo importa `dataclasses, datetime, decimal, enum, typing, abc, threading`. `tests/test_arquitectura.py` lo verifica leyendo los imports (AST). |
| DIP | Los casos de uso reciben puertos por constructor (`config.py` los ensambla). Los adaptadores implementan los puertos; el dominio nunca los importa. |
| Entidades | `Evento`, `Asiento`, `Cliente`, `Orden`, `Boleto` en `modelo.py`, objetos puros. |
| Bloqueo de 10 min | `Orden.expira_en`; el estado de cada asiento se **deriva** de las órdenes (`calcular_disponibilidad`), así que expira aunque el temporizador falle. `ServicioLiberacionBloqueos` marca las órdenes como EXPIRADA. |
| Tarifas y descuentos | `CalculadoraTarifas` (1-2: 10 %/0 %; 3-5: 8 %/5 %; 6: 5 %/10 %). |
| Máx. 6 boletas por cliente y evento | `ServicioCompra` (cuenta aprobadas + bloqueos vigentes). |
| Emisión y firma | `ServicioPagos` emite boletas solo con pago aprobado; firma HMAC-SHA256 con clave derivada del evento (`HmacCredenciales`). `ValidarBoletoUseCase` recalcula y compara. |
| Persistencia dual | Puertos `EventoRepositorio`/`RecintoRepositorio` (MySQL legacy, solo lectura) y `OrdenRepositorio`/`BoletoRepositorio` (MongoDB). |
| Pasarelas homogéneas | Puerto `PasarelaPagoPuerto`; adaptadores PayPal, Wompi y PSE traducen su propio formato a `ConfirmacionPago`. |
| Servicios externos | Puertos de credenciales/QR, notificación (WhatsApp, SendGrid) y facturación (DIAN). |
| Adaptadores primarios | REST (compra, selección de asientos y webhook de pagos) y temporizador. |

## Adaptadores: completos vs mock (entregable: al menos dos completos)

* **Completos y probados:** REST (primario), temporizador (primario), `HmacCredenciales`, repositorios MongoDB
  (probados con `mongomock`, no con un MongoDB real), `RelojSistema`, `GeneradorUuid`.
* **Implementado pero no probado contra un servidor real:** repositorios MySQL (se probaron con SQLite, que valida
  el mapeo y las consultas, pero no el driver `mysql-connector`).
* **Mock:** PayPal, Wompi, PSE, SendGrid, WhatsApp, DIAN y los repositorios en memoria.
  Los formatos de notificación de las pasarelas son versiones simplificadas, no verificadas contra su API real.

## Supuestos y decisiones (revísalos con tu equipo)

1. Tarifa y descuento se calculan sobre el valor base (suma de precios base): total = base + tarifa − descuento.
2. "Más de 5 boletos" solo puede ser 6, porque el límite por cliente y evento es 6.
3. El estado de un asiento (Bloqueado/Vendido) no se guarda: se deduce de las órdenes en MongoDB. El MySQL legacy
   solo aporta recintos, aforos, asientos y eventos (se asumió que los eventos también viven allí).
4. `Boleto` lleva `asiento_id` (un boleto por asiento) y `Orden` lleva `numero_factura`; el enunciado no los lista.
5. La clave secreta del evento no está en el dominio: el adaptador la deriva de una clave maestra.
6. La imagen QR no se dibuja; el puerto entrega el texto que codificaría (`representacion_grafica`).

## Limitaciones conocidas

* El candado anti doble-reserva (`threading.Lock`) protege un solo proceso. Con varias instancias hace falta una
  operación atómica en la base (por ejemplo un índice único por evento y asiento en MongoDB).
* Los webhooks no verifican firma de la pasarela (los mocks no la tienen).
* Un pago aprobado que llega después de expirar el bloqueo deja la orden EXPIRADA; el reembolso no está modelado.
* La clave maestra por defecto en `config.py` es solo para demo: en producción va en `STAGEPASS_CLAVE`.
