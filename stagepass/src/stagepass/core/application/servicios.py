"""Casos de uso: implementan los puertos primarios y orquestan el dominio usando puertos secundarios."""
from __future__ import annotations

import threading
from typing import Dict, List

from ..domain import reglas
from ..domain.excepciones import (AsientoNoDisponible, BoletoNoEncontrado, ClienteInvalido,
                                  ErrorFacturacion, ErrorNotificacion, ErrorPasarela,
                                  EventoNoDisponible, EventoNoEncontrado,
                                  LimiteBoletosExcedido, OrdenNoEncontrada,
                                  PasarelaDesconocida, SeleccionInvalida)
from ..domain.modelo import (Asiento, Boleto, Cliente, EstadoAsiento, EstadoEvento, EstadoOrden, EstadoPago,
                             Evento, Mensaje, Orden, ResultadoValidacion)
from ..ports.entrada import (ComandoIniciarCompra, ConfirmarPagoUseCase,
                             ConsultarCatalogoUseCase, ConsultarOrdenUseCase,
                             IniciarCompraUseCase, LiberarBloqueosExpiradosUseCase,
                             ResultadoCompra, ValidarBoletoUseCase)
from ..ports.salida import (BoletoRepositorio, EventoRepositorio, FacturacionElectronicaPuerto,
                            GeneradorCredencialesPuerto, GeneradorIdentificadoresPuerto,
                            NotificacionPuerto, OrdenRepositorio, PasarelaPagoPuerto,
                            RecintoRepositorio, RelojPuerto)


class ServicioCatalogo(ConsultarCatalogoUseCase):
    def __init__(self, eventos: EventoRepositorio, recintos: RecintoRepositorio,
                 ordenes: OrdenRepositorio, reloj: RelojPuerto):
        self._eventos, self._recintos, self._ordenes, self._reloj = eventos, recintos, ordenes, reloj

    def listar_eventos(self) -> List[Evento]:
        return self._eventos.listar()

    def asientos_del_evento(self, evento_id: str) -> List[Asiento]:
        evento = self._eventos.obtener(evento_id)
        if evento is None:
            raise EventoNoEncontrado(f"Evento {evento_id} no existe")
        return reglas.calcular_disponibilidad(
            self._recintos.listar_asientos(evento.recinto_id),
            self._ordenes.listar_por_evento(evento_id), self._reloj.ahora())


class ServicioCompra(IniciarCompraUseCase):
    def __init__(self, eventos: EventoRepositorio, recintos: RecintoRepositorio,
                 ordenes: OrdenRepositorio, pasarelas: Dict[str, PasarelaPagoPuerto],
                 reloj: RelojPuerto, ids: GeneradorIdentificadoresPuerto):
        self._eventos, self._recintos, self._ordenes = eventos, recintos, ordenes
        self._pasarelas, self._reloj, self._ids = pasarelas, reloj, ids
        self._calculadora = reglas.CalculadoraTarifas()
        self._candado = threading.Lock()  # evita doble reserva dentro de un mismo proceso

    def iniciar_compra(self, c: ComandoIniciarCompra) -> ResultadoCompra:
        cliente = self._validar_cliente(c)
        if len(set(c.asientos_ids)) != len(c.asientos_ids) or not c.asientos_ids:
            raise SeleccionInvalida("La selección está vacía o repite asientos")
        if len(c.asientos_ids) > reglas.MAX_BOLETOS_POR_CLIENTE_Y_EVENTO:
            raise LimiteBoletosExcedido(
                f"Máximo {reglas.MAX_BOLETOS_POR_CLIENTE_Y_EVENTO} boletas por cliente y evento")
        pasarela = self._pasarelas.get(c.pasarela)
        if pasarela is None:
            raise PasarelaDesconocida(f"Pasarela '{c.pasarela}' no soportada")
        evento = self._eventos.obtener(c.evento_id)
        if evento is None:
            raise EventoNoEncontrado(f"Evento {c.evento_id} no existe")
        if evento.estado != EstadoEvento.PROGRAMADO:
            raise EventoNoDisponible(f"El evento está {evento.estado.value}")

        with self._candado:
            ahora = self._reloj.ahora()
            catalogo = {a.id: a for a in self._recintos.listar_asientos(evento.recinto_id)}
            desconocidos = [i for i in c.asientos_ids if i not in catalogo]
            if desconocidos:
                raise SeleccionInvalida("Asientos inexistentes: " + ", ".join(desconocidos))
            con_estado = {a.id: a for a in reglas.calcular_disponibilidad(
                catalogo.values(), self._ordenes.listar_por_evento(evento.id), ahora)}
            ocupados = [i for i in c.asientos_ids if con_estado[i].estado != EstadoAsiento.DISPONIBLE]
            if ocupados:
                raise AsientoNoDisponible(ocupados)
            previas = reglas.boletos_activos(
                self._ordenes.listar_por_cliente_y_evento(cliente.id, evento.id), ahora)
            if previas + len(c.asientos_ids) > reglas.MAX_BOLETOS_POR_CLIENTE_Y_EVENTO:
                raise LimiteBoletosExcedido(
                    f"El cliente ya tiene {previas} boletas; el máximo por evento es "
                    f"{reglas.MAX_BOLETOS_POR_CLIENTE_Y_EVENTO}")
            elegidos = [con_estado[i] for i in c.asientos_ids]
            tarifa = self._calculadora.calcular(elegidos)
            orden = Orden(id=self._ids.nuevo_id(), evento_id=evento.id, cliente=cliente,
                          asientos=elegidos, tarifa_servicio=tarifa.tarifa_servicio,
                          descuento=tarifa.descuento, monto_total=tarifa.total,
                          expira_en=reglas.instante_expiracion(ahora))
            self._ordenes.guardar(orden)  # desde aquí los asientos quedan bloqueados

        try:
            solicitud = pasarela.registrar_pago(orden)
        except ErrorPasarela:
            orden.rechazar()
            self._ordenes.guardar(orden)
            raise
        orden.referencia_pago = solicitud.referencia
        self._ordenes.guardar(orden)
        return ResultadoCompra(orden, solicitud)

    @staticmethod
    def _validar_cliente(c: ComandoIniciarCompra) -> Cliente:
        correo = (c.correo or "").strip().lower()
        if not c.nombre_completo.strip() or "@" not in correo or not c.telefono_movil.strip():
            raise ClienteInvalido("Nombre, correo válido y teléfono móvil son obligatorios")
        return Cliente(c.cliente_id or correo, c.nombre_completo.strip(), correo,
                       c.telefono_movil.strip(), c.nacionalidad.strip())


class ServicioPagos(ConfirmarPagoUseCase):
    def __init__(self, ordenes: OrdenRepositorio, boletos: BoletoRepositorio,
                 pasarelas: Dict[str, PasarelaPagoPuerto], credenciales: GeneradorCredencialesPuerto,
                 facturacion: FacturacionElectronicaPuerto, notificadores: List[NotificacionPuerto],
                 reloj: RelojPuerto, ids: GeneradorIdentificadoresPuerto):
        self._ordenes, self._boletos, self._pasarelas = ordenes, boletos, pasarelas
        self._credenciales, self._facturacion = credenciales, facturacion
        self._notificadores, self._reloj, self._ids = notificadores, reloj, ids

    def confirmar_pago(self, pasarela: str, notificacion: dict) -> Orden:
        puerto = self._pasarelas.get(pasarela)
        if puerto is None:
            raise PasarelaDesconocida(f"Pasarela '{pasarela}' no soportada")
        confirmacion = puerto.interpretar_confirmacion(notificacion)
        orden = self._ordenes.obtener(confirmacion.orden_id)
        if orden is None:
            raise OrdenNoEncontrada(f"Orden {confirmacion.orden_id} no existe")
        if orden.estado != EstadoOrden.PENDIENTE_PAGO:
            return orden  # notificación repetida: operación idempotente
        if orden.esta_expirada(self._reloj.ahora()):
            orden.expirar()
            self._ordenes.guardar(orden)
            return orden
        if confirmacion.estado == EstadoPago.PENDIENTE:
            return orden
        if confirmacion.estado == EstadoPago.RECHAZADO:
            orden.rechazar()
            self._ordenes.guardar(orden)
            return orden

        orden.aprobar(confirmacion.referencia)
        ahora = self._reloj.ahora()
        boletos = []
        for asiento in orden.asientos:
            codigo = self._credenciales.generar_codigo_redencion()
            firma = self._credenciales.firmar(
                orden.evento_id, reglas.datos_para_firma(orden, asiento.id, codigo))
            boletos.append(Boleto(self._ids.nuevo_id(), orden.id, orden.evento_id, asiento.id,
                                  codigo, firma, ahora))
        try:
            orden.numero_factura = self._facturacion.emitir_factura(orden).numero
        except ErrorFacturacion:
            orden.numero_factura = None  # la factura puede reintentarse; no se revierte la venta
        self._boletos.guardar_todos(boletos)
        self._ordenes.guardar(orden)
        self._notificar(orden, boletos)
        return orden

    def _notificar(self, orden: Orden, boletos: List[Boleto]) -> None:
        codigos = ", ".join(b.codigo_redencion for b in boletos)
        mensaje = Mensaje("Tus boletas de StagePass Live",
                          f"Hola {orden.cliente.nombre_completo}, tu orden {orden.id} fue aprobada. "
                          f"Códigos de redención: {codigos}")
        for notificador in self._notificadores:
            try:
                notificador.enviar(orden.cliente, mensaje)
            except ErrorNotificacion:
                pass  # una notificación fallida no debe deshacer una venta aprobada


class ServicioConsultaOrdenes(ConsultarOrdenUseCase):
    def __init__(self, ordenes: OrdenRepositorio, boletos: BoletoRepositorio):
        self._ordenes, self._boletos = ordenes, boletos

    def obtener_orden(self, orden_id: str) -> Orden:
        orden = self._ordenes.obtener(orden_id)
        if orden is None:
            raise OrdenNoEncontrada(f"Orden {orden_id} no existe")
        return orden

    def boletos_de_orden(self, orden_id: str) -> List[Boleto]:
        self.obtener_orden(orden_id)
        return self._boletos.listar_por_orden(orden_id)


class ServicioValidacionBoletos(ValidarBoletoUseCase):
    def __init__(self, ordenes: OrdenRepositorio, boletos: BoletoRepositorio,
                 credenciales: GeneradorCredencialesPuerto):
        self._ordenes, self._boletos, self._credenciales = ordenes, boletos, credenciales

    def validar(self, codigo_redencion: str) -> ResultadoValidacion:
        boleto = self._boletos.obtener_por_codigo(codigo_redencion)
        if boleto is None:
            raise BoletoNoEncontrado("Código de redención desconocido")
        orden = self._ordenes.obtener(boleto.orden_id)
        if orden is None or orden.estado != EstadoOrden.APROBADA:
            return ResultadoValidacion(False, "La orden asociada no está aprobada", boleto)
        datos = reglas.datos_para_firma(orden, boleto.asiento_id, boleto.codigo_redencion)
        if not self._credenciales.verificar(boleto.evento_id, datos, boleto.firma_hash):
            return ResultadoValidacion(False, "Firma inválida", boleto)
        return ResultadoValidacion(True, "Boleto auténtico", boleto)


class ServicioLiberacionBloqueos(LiberarBloqueosExpiradosUseCase):
    def __init__(self, ordenes: OrdenRepositorio, reloj: RelojPuerto):
        self._ordenes, self._reloj = ordenes, reloj

    def liberar_expirados(self) -> int:
        vencidas = self._ordenes.listar_pendientes_expiradas(self._reloj.ahora())
        for orden in vencidas:
            orden.expirar()
            self._ordenes.guardar(orden)
        return len(vencidas)
