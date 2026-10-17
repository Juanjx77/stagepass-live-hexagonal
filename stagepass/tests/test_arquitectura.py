"""Pruebas de soberanía del núcleo: ningún archivo de core/ importa infraestructura."""
import ast
import pathlib
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent / "src" / "stagepass"
PERMITIDOS = {"__future__", "abc", "dataclasses", "datetime", "decimal", "enum", "typing", "threading"}


def importaciones(ruta):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                yield a.name.split(".")[0], 0
        elif isinstance(nodo, ast.ImportFrom):
            yield (nodo.module or "").split(".")[0], nodo.level


class TestAislamiento(unittest.TestCase):
    def test_el_nucleo_solo_importa_dominio_y_biblioteca_estandar(self):
        for ruta in (RAIZ / "core").rglob("*.py"):
            for modulo, nivel in importaciones(ruta):
                if nivel > 0:
                    continue  # importación relativa dentro del propio núcleo
                self.assertIn(modulo, PERMITIDOS, f"{ruta.name} importa '{modulo}'")

    def test_los_puertos_no_dependen_de_casos_de_uso_ni_de_adaptadores(self):
        for ruta in (RAIZ / "core" / "ports").glob("*.py"):
            texto = ruta.read_text(encoding="utf-8")
            self.assertNotIn("application", texto.replace("..", ""), ruta.name)
            self.assertNotIn("adapters", texto, ruta.name)

    def test_los_adaptadores_secundarios_implementan_puertos(self):
        # Cada clase concreta de adaptadores secundarios debe heredar de un puerto del núcleo.
        for ruta in (RAIZ / "adapters" / "secondary").rglob("*.py"):
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for nodo in arbol.body:
                if isinstance(nodo, ast.ClassDef) and not nodo.name.startswith("_"):
                    bases = [getattr(b, "id", "") for b in nodo.bases]
                    self.assertTrue(bases, f"{ruta.name}:{nodo.name} no implementa ningún puerto")


if __name__ == "__main__":
    unittest.main()
