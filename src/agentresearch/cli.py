"""Interfaz de línea de comandos de agentresearch."""

import argparse
from importlib.metadata import version


def construir_analizador() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos de la CLI."""
    analizador = argparse.ArgumentParser(prog="agentresearch")
    analizador.add_argument(
        "--version",
        action="version",
        version=f"agentresearch {version('agentresearch')}",
    )
    return analizador


def main() -> None:
    """Punto de entrada de la CLI."""
    analizador = construir_analizador()
    analizador.parse_args()


if __name__ == "__main__":
    main()
