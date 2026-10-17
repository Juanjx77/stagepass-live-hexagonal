"""Excepciones de negocio. Pertenecen al núcleo: no dependen de ninguna librería externa."""


class ErrorDominio(Exception):
    """Base de todos los errores de negocio."""


class EventoNoDisponible(ErrorDominio):
    pass


class EventoNoEncontrado(ErrorDominio):
    pass


class OrdenNoEncontrada(ErrorDominio):
    pass


class BoletoNoEncontrado(ErrorDominio):
    pass


class SeleccionInvalida(ErrorDominio):
    pass


class ClienteInvalido(ErrorDominio):
    pass


class PasarelaDesconocida(ErrorDominio):
    pass


class AsientoNoDisponible(ErrorDominio):
    def __init__(self, asientos_ids):
        super().__init__("Asientos no disponibles: " + ", ".join(asientos_ids))
        self.asientos_ids = list(asientos_ids)


class LimiteBoletosExcedido(ErrorDominio):
    pass


class TransicionOrdenInvalida(ErrorDominio):
    pass


# Errores que los adaptadores traducen desde sus tecnologías hacia el dominio
class ErrorPasarela(ErrorDominio):
    pass


class ErrorNotificacion(ErrorDominio):
    pass


class ErrorFacturacion(ErrorDominio):
    pass
