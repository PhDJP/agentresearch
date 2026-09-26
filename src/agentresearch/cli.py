"""Interfaz de línea de comandos de agentresearch."""

import argparse
import io
import json
import sys
from importlib.metadata import version
from pathlib import Path

from agentresearch.protocolo import validar_archivo
from agentresearch.trazabilidad import Anclaje, RegistroEncadenado

RUTA_PROTOCOLO_POR_DEFECTO = Path("protocolo") / "protocolo.yaml"


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
    verificar.add_argument(
        "--anclaje",
        type=_anclaje_argumento,
        help="exige que el registro cumpla este anclaje (evt-NNNNNN@sha256:<hex>)",
    )

    protocolo = subcomandos.add_parser("protocolo", help="Operaciones sobre el protocolo")
    subcomandos_protocolo = protocolo.add_subparsers(dest="subcomando", required=True)

    validar = subcomandos_protocolo.add_parser(
        "validar", help="Valida el protocolo contra el esquema y las reglas metodológicas"
    )
    validar.add_argument(
        "ruta",
        type=Path,
        nargs="?",
        default=RUTA_PROTOCOLO_POR_DEFECTO,
        help=f"archivo del protocolo (por defecto, {RUTA_PROTOCOLO_POR_DEFECTO.as_posix()})",
    )
    validar.add_argument(
        "--json",
        dest="como_json",
        action="store_true",
        help="imprime el resultado en JSON, para que lo interprete Claude Code",
    )

    return analizador


def _anclaje_argumento(texto: str) -> Anclaje:
    try:
        return Anclaje.desde_texto(texto)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def ejecutar_registro_verificar(archivo: Path, anclaje: Anclaje | None = None) -> int:
    """Verifica un registro encadenado e imprime el resultado. Devuelve el código de salida."""
    registro = RegistroEncadenado(archivo)
    resultado = registro.verificar(anclaje)
    if resultado.valido:
        print(f"íntegro: {archivo}")
        if anclaje is not None:
            print(f"cumple el anclaje: {anclaje}")
        print(f"anclaje actual: {registro.anclaje()}")
        return 0
    if resultado.numero_linea_error is not None:
        print(f"inválido en la línea {resultado.numero_linea_error}: {resultado.mensaje}")
    else:
        print(f"inválido: {resultado.mensaje}")
    return 1


def ejecutar_protocolo_validar(ruta: Path, como_json: bool = False) -> int:
    """Valida un protocolo e imprime los hallazgos.

    Devuelve 1 si hay errores y 0 si no los hay, aunque haya advertencias.
    """
    resultado = validar_archivo(ruta)
    if como_json:
        # ASCII escapado: JSON válido aunque la consola no use UTF-8.
        print(json.dumps(resultado.como_dict(), ensure_ascii=True, indent=2))
        return 0 if resultado.valido else 1

    _tolerar_caracteres_no_representables()
    descripcion = f"protocolo: {ruta}"
    if resultado.estado is not None:
        descripcion += f" ({resultado.estado}, versión {resultado.version_protocolo})"
    print(descripcion)
    for hallazgo in resultado.hallazgos:
        print(hallazgo)
    print(f"resultado: {_resumen(len(resultado.errores), len(resultado.advertencias))}")
    return 0 if resultado.valido else 1


def _resumen(errores: int, advertencias: int) -> str:
    if errores == 0 and advertencias == 0:
        return "sin errores ni advertencias"
    texto_errores = f"{errores} error" + ("" if errores == 1 else "es")
    texto_advertencias = f"{advertencias} advertencia" + ("" if advertencias == 1 else "s")
    return f"{texto_errores}, {texto_advertencias}"


def _tolerar_caracteres_no_representables() -> None:
    """Evita que un carácter fuera de la codificación de la consola rompa la salida."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")


def main() -> None:
    """Punto de entrada de la CLI."""
    analizador = construir_analizador()
    argumentos = analizador.parse_args()

    if argumentos.comando is None:
        analizador.print_help()
        return

    if argumentos.comando == "registro" and argumentos.subcomando == "verificar":
        sys.exit(ejecutar_registro_verificar(argumentos.archivo, argumentos.anclaje))

    if argumentos.comando == "protocolo" and argumentos.subcomando == "validar":
        sys.exit(ejecutar_protocolo_validar(argumentos.ruta, argumentos.como_json))


if __name__ == "__main__":
    main()
