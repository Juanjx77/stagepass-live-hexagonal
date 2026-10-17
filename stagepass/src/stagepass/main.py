"""Punto de entrada. Uso:  PYTHONPATH=src python -m stagepass.main [--real] [--puerto 8000]"""
import argparse
import logging

from stagepass import config
from stagepass.adapters.primary.programador import ProgramadorLiberacion
from stagepass.adapters.primary.rest_api import crear_servidor


def main() -> None:
    parser = argparse.ArgumentParser(description="StagePass Live")
    parser.add_argument("--real", action="store_true", help="usar MySQL legacy + MongoDB")
    parser.add_argument("--puerto", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    app = config.aplicacion_real() if args.real else config.aplicacion_en_memoria()
    ProgramadorLiberacion(app.liberacion, 30).iniciar()
    servidor = crear_servidor(app, "0.0.0.0", args.puerto)
    print(f"StagePass Live en http://localhost:{args.puerto}  (modo {'real' if args.real else 'memoria'})")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
