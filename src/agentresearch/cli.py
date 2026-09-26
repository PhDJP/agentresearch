"""Interfaz de línea de comandos de agentresearch."""

import argparse
import sys
from importlib.metadata import version
from pathlib import Path

from agentresearch.trazabilidad import RegistroEncadenado


def construir_analizador() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos de la CLI."""
    analizador = argparse.ArgumentParser(prog="agentresearch")
    analizador.add_argument(
        "--version",
        action="version",
        version=f"agentresearch {version('agentresearch')}",
    )
    subcomandos = analizador.add_subparsers(dest="comando")

    registro = subcomandos.add_parser("registro", help="Operaciones sobre registros encadenados")
    subcomandos_registro = registro.add_subparsers(dest="subcomando", required=True)

    verificar = subcomandos_registro.add_parser(
        "verificar", help="Verifica la integridad de un registro encadenado"
    )
    verificar.add_argument("archivo", type=Path)

    return analizador


def ejecutar_registro_verificar(archivo: Path) -> int:
    """Verifica un registro encadenado e imprime el resultado. Devuelve el código de salida."""
    resultado = RegistroEncadenado(archivo).verificar()
    if resultado.valido:
        print(f"íntegro: {archivo}")
        return 0
    if resultado.numero_linea_error is not None:
        print(f"inválido en la línea {resultado.numero_linea_error}: {resultado.mensaje}")
    else:
        print(f"inválido: {resultado.mensaje}")
    return 1


def main() -> None:
    """Punto de entrada de la CLI."""
    analizador = construir_analizador()
    argumentos = analizador.parse_args()

    if argumentos.comando is None:
        analizador.print_help()
        return

    if argumentos.comando == "registro" and argumentos.subcomando == "verificar":
        sys.exit(ejecutar_registro_verificar(argumentos.archivo))


if __name__ == "__main__":
    main()
