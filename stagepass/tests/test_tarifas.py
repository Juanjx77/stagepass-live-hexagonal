import unittest
from decimal import Decimal

from stagepass.core.domain.excepciones import SeleccionInvalida
from stagepass.core.domain.modelo import Asiento
from stagepass.core.domain.reglas import CalculadoraTarifas


def asientos(n, precio="100000"):
    return [Asiento(f"a{i}", "R", f"S{i}", Decimal(precio)) for i in range(n)]


class TestTarifas(unittest.TestCase):
    def setUp(self):
        self.calc = CalculadoraTarifas()

    def test_uno_o_dos_boletos(self):
        for n in (1, 2):
            r = self.calc.calcular(asientos(n))
            base = Decimal("100000") * n
            self.assertEqual(r.tarifa_servicio, base * Decimal("0.10"))
            self.assertEqual(r.descuento, Decimal("0.00"))
            self.assertEqual(r.total, base * Decimal("1.10"))

    def test_tres_a_cinco_boletos(self):
        for n in (3, 5):
            r = self.calc.calcular(asientos(n))
            base = Decimal("100000") * n
            self.assertEqual(r.tarifa_servicio, base * Decimal("0.08"))
            self.assertEqual(r.descuento, base * Decimal("0.05"))
            self.assertEqual(r.total, base * Decimal("1.03"))

    def test_compra_corporativa_mas_de_cinco(self):
        r = self.calc.calcular(asientos(6))
        self.assertEqual(r.tarifa_servicio, Decimal("30000.00"))
        self.assertEqual(r.descuento, Decimal("60000.00"))
        self.assertEqual(r.total, Decimal("570000.00"))

    def test_seleccion_vacia(self):
        with self.assertRaises(SeleccionInvalida):
            self.calc.calcular([])

    def test_redondeo_a_centavos(self):
        r = self.calc.calcular(asientos(1, "33333.33"))
        self.assertEqual(r.tarifa_servicio, Decimal("3333.33"))


if __name__ == "__main__":
    unittest.main()
