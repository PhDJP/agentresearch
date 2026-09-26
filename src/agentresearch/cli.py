"""Interfaz de línea de comandos de agentresearch."""

import argparse
import io
import json
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, Protocol

from agentresearch.protocolo import validar_archivo
from agentresearch.protocolo.aprobacion import (
    ErrorCicloDeVida,
    NivelElegido,
    OperacionCancelada,
    Reloj,
    ResultadoOperacion,
    aprobar,
    enmendar,
    simular_enmienda,
    texto_de_cambios,
)
from agentresearch.protocolo.decisiones import (
    ResultadoConfirmacion,
    confirmar_decisiones,
    registrar_decision,
)
from agentresearch.protocolo.historial import construir_historial, texto_historial
from agentresearch.protocolo.terminal import Terminal, TerminalDelSistema
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
    _argumento_ruta(validar)
    _argumento_json(validar)

    aprobar_parser = subcomandos_protocolo.add_parser(
        "aprobar",
        help="Aprueba el borrador del protocolo (exige una terminal interactiva)",
    )
    _argumento_ruta(aprobar_parser)
    aprobar_parser.add_argument(
        "--aprobado-por",
        required=True,
        metavar="ID",
        help="revisor humano declarado en seleccion.revisores que aprueba el protocolo",
    )
    aprobar_parser.add_argument(
        "--justificaciones",
        type=Path,
        metavar="ARCHIVO",
        help="JSON con la justificación de cada advertencia activa; las que falten se piden",
    )
    _argumento_json(aprobar_parser)

    enmendar_parser = subcomandos_protocolo.add_parser(
        "enmendar",
        help="Registra una enmienda del protocolo vigente (exige una terminal interactiva)",
    )
    _argumento_ruta(enmendar_parser)
    enmendar_parser.add_argument(
        "--nivel",
        choices=["mayor", "menor"],
        help="mayor si puede cambiar qué estudios se incluyen o cómo se clasifican; menor si "
        "no (el parche lo asigna el paquete)",
    )
    enmendar_parser.add_argument(
        "--enmendado-por",
        metavar="ID",
        help="revisor humano declarado en seleccion.revisores que registra la enmienda",
    )
    enmendar_parser.add_argument("--justificacion", metavar="TEXTO")
    enmendar_parser.add_argument("--efecto-esperado", metavar="TEXTO")
    enmendar_parser.add_argument(
        "--archivo-enmienda",
        type=Path,
        metavar="ARCHIVO",
        help="JSON con justificacion y efecto_esperado, en lugar de las dos opciones",
    )
    enmendar_parser.add_argument(
        "--simular",
        action="store_true",
        help="muestra el diff y la versión siguiente sin escribir nada",
    )
    _argumento_json(enmendar_parser)

    historial = subcomandos_protocolo.add_parser(
        "historial",
        help="Muestra versiones, enmiendas, decisiones y el anclaje del registro",
    )
    _argumento_ruta(historial)
    _argumento_json(historial)

    decision = subcomandos_protocolo.add_parser(
        "decision", help="Decisiones del protocolo: registrar la propuesta y confirmarla"
    )
    subcomandos_decision = decision.add_subparsers(dest="accion", required=True)
    registrar = subcomandos_decision.add_parser(
        "registrar", help="Registra una decisión como propuesta pendiente de confirmar"
    )
    registrar.add_argument(
        "--archivo",
        type=Path,
        required=True,
        metavar="ARCHIVO",
        help="JSON con la decisión: opciones, elegida, justificación y quién propuso y decidió",
    )
    _argumento_protocolo(registrar)
    _argumento_json(registrar)
    confirmar = subcomandos_decision.add_parser(
        "confirmar",
        help="Confirma en lote las decisiones pendientes (exige una terminal interactiva)",
    )
    confirmar.add_argument(
        "--confirmado-por",
        required=True,
        metavar="ID",
        help="revisor humano que decidió; se confirman sus decisiones pendientes",
    )
    _argumento_protocolo(confirmar)
    _argumento_json(confirmar)

    return analizador


def _argumento_protocolo(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--protocolo",
        type=Path,
        default=RUTA_PROTOCOLO_POR_DEFECTO,
        metavar="RUTA",
        help=f"archivo del protocolo (por defecto, {RUTA_PROTOCOLO_POR_DEFECTO.as_posix()})",
    )


def _argumento_ruta(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "ruta",
        type=Path,
        nargs="?",
        default=RUTA_PROTOCOLO_POR_DEFECTO,
        help=f"archivo del protocolo (por defecto, {RUTA_PROTOCOLO_POR_DEFECTO.as_posix()})",
    )


def _argumento_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        dest="como_json",
        action="store_true",
        help="imprime el resultado en JSON, para que lo interprete Claude Code",
    )


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
    registro = resultado.registro
    if registro is not None and registro["existe"]:
        anclaje = f", anclaje {registro['anclaje']}" if registro["anclaje"] else ""
        print(f"registro: {registro['ruta']} ({registro['numero_eventos']} eventos{anclaje})")
    for hallazgo in resultado.hallazgos:
        print(hallazgo)
    print(f"resultado: {_resumen(len(resultado.errores), len(resultado.advertencias))}")
    return 0 if resultado.valido else 1


def ejecutar_protocolo_aprobar(
    ruta: Path,
    aprobado_por: str,
    justificaciones: Path | None = None,
    como_json: bool = False,
    terminal: Terminal | None = None,
    reloj: Reloj | None = None,
) -> int:
    """Aprueba el protocolo tras la confirmación interactiva del investigador."""
    return _ejecutar_operacion(
        "protocolo aprobar",
        como_json,
        lambda: aprobar(ruta, aprobado_por, _terminal(terminal), justificaciones, reloj),
        _describir_operacion,
    )


def ejecutar_protocolo_enmendar(
    ruta: Path,
    nivel: NivelElegido | None = None,
    enmendado_por: str | None = None,
    justificacion: str | None = None,
    efecto_esperado: str | None = None,
    archivo_enmienda: Path | None = None,
    simular: bool = False,
    como_json: bool = False,
    terminal: Terminal | None = None,
    reloj: Reloj | None = None,
) -> int:
    """Registra una enmienda tras la confirmación interactiva, o la simula sin escribir."""
    if simular:
        return _ejecutar_simulacion(ruta, nivel, como_json)
    return _ejecutar_operacion(
        "protocolo enmendar",
        como_json,
        lambda: enmendar(
            ruta,
            nivel,
            enmendado_por,
            _terminal(terminal),
            justificacion,
            efecto_esperado,
            archivo_enmienda,
            reloj,
        ),
        _describir_operacion,
    )


def _ejecutar_simulacion(ruta: Path, nivel: NivelElegido | None, como_json: bool) -> int:
    """Simula una enmienda: 0 si se podría registrar, 1 si algo lo impediría."""
    _tolerar_caracteres_no_representables()
    comando = "protocolo enmendar --simular"
    try:
        propuesta = simular_enmienda(ruta, nivel)
    except ErrorCicloDeVida as error:
        return _informar_fallo(comando, como_json, "no se pudo simular", error.errores)
    if como_json:
        _imprimir_json(comando, not propuesta.problemas, propuesta.problemas, propuesta.como_dict())
        return 0 if not propuesta.problemas else 1
    print(f"simulación de enmienda: {propuesta.ruta_protocolo}")
    print(f"versión registrada: {propuesta.version_registrada} ({propuesta.evento_registrado})")
    if propuesta.version_siguiente is not None:
        print(f"versión siguiente: {propuesta.version_siguiente} (nivel {propuesta.nivel})")
    else:
        opciones = propuesta.opciones_de_version
        print(
            f"versión siguiente: {opciones['menor']} si es menor, {opciones['mayor']} si es mayor"
        )
    for linea in texto_de_cambios(propuesta.cambios):
        print(linea)
    if propuesta.problemas:
        print("impedirían enmendar:")
        for problema in propuesta.problemas:
            print(f"  - {problema}")
        return 1
    return 0


def ejecutar_protocolo_historial(ruta: Path, como_json: bool = False) -> int:
    """Muestra el historial del protocolo. Devuelve 1 si el registro no es fiable (P-E10)."""
    _tolerar_caracteres_no_representables()
    historial = construir_historial(ruta)
    codigo = 0 if historial.integro else 1
    if como_json:
        errores = [str(h) for h in historial.hallazgos if h.id_regla == "P-E10"]
        _imprimir_json("protocolo historial", historial.integro, errores, historial.como_dict())
        return codigo
    for linea in texto_historial(historial):
        print(linea)
    return codigo


def ejecutar_decision_registrar(
    archivo: Path,
    protocolo: Path = RUTA_PROTOCOLO_POR_DEFECTO,
    como_json: bool = False,
    reloj: Reloj | None = None,
) -> int:
    """Registra una decisión del protocolo como propuesta pendiente de confirmar."""
    return _ejecutar_operacion(
        "protocolo decision registrar",
        como_json,
        lambda: registrar_decision(protocolo, archivo, reloj),
        lambda resultado: [
            f"decisión {resultado.id_decision} registrada como propuesta "
            f"({resultado.evento.id}); queda pendiente de confirmar",
            "el investigador la confirma en su terminal con: agentresearch protocolo decision "
            "confirmar --confirmado-por <id>",
            f"anclaje: {resultado.anclaje}",
        ],
    )


def ejecutar_decision_confirmar(
    confirmado_por: str,
    protocolo: Path = RUTA_PROTOCOLO_POR_DEFECTO,
    como_json: bool = False,
    terminal: Terminal | None = None,
    reloj: Reloj | None = None,
) -> int:
    """Confirma en lote las decisiones pendientes tras la confirmación interactiva."""
    return _ejecutar_operacion(
        "protocolo decision confirmar",
        como_json,
        lambda: confirmar_decisiones(protocolo, confirmado_por, _terminal(terminal), reloj),
        _describir_confirmacion,
    )


def _describir_confirmacion(resultado: ResultadoConfirmacion) -> list[str]:
    if not resultado.eventos:
        lineas = [f"no hay decisiones pendientes de {resultado.confirmado_por}"]
    else:
        lineas = [
            f"decisiones confirmadas por {resultado.confirmado_por}: "
            f"{', '.join(resultado.confirmadas)}",
            f"anclaje: {resultado.anclaje}",
        ]
    if resultado.pendientes_de_otros:
        lineas.append(f"pendientes de otros revisores: {', '.join(resultado.pendientes_de_otros)}")
    return lineas


def _terminal(terminal: Terminal | None) -> Terminal:
    return terminal if terminal is not None else TerminalDelSistema()


def _describir_operacion(resultado: ResultadoOperacion) -> list[str]:
    operacion = "aprobado" if resultado.evento.tipo == "protocolo_aprobado" else "enmendado"
    return [
        f"protocolo {operacion}: {resultado.ruta_protocolo} "
        f"(versión {resultado.version_anterior} → {resultado.version_protocolo})",
        f"hash: {resultado.hash_protocolo}",
        f"evento: {resultado.evento.id} ({resultado.evento.tipo})",
        f"copia de la versión: {resultado.ruta_version}",
        f"anclaje: {resultado.anclaje}",
    ]


class _ConDiccionario(Protocol):
    def como_dict(self) -> dict[str, Any]: ...


def _ejecutar_operacion[R: _ConDiccionario](
    comando: str,
    como_json: bool,
    operacion: Callable[[], R],
    describir: Callable[[R], list[str]],
) -> int:
    """Ejecuta una operación del ciclo de vida e imprime su resultado en texto o en JSON.

    Devuelve 0 si se completó y 1 si se rechazó o se canceló (sin escribir nada).
    """
    _tolerar_caracteres_no_representables()
    try:
        resultado = operacion()
    except ErrorCicloDeVida as error:
        return _informar_fallo(comando, como_json, "no se pudo completar", error.errores)
    except OperacionCancelada as error:
        return _informar_fallo(comando, como_json, "cancelado", [f"cancelado: {error}"])
    if como_json:
        _imprimir_json(comando, True, [], resultado.como_dict())
    else:
        for linea in describir(resultado):
            print(linea)
    return 0


def _informar_fallo(comando: str, como_json: bool, motivo: str, errores: list[str]) -> int:
    if como_json:
        _imprimir_json(comando, False, errores, None)
    else:
        print(f"{comando}: {motivo}")
        for error in errores:
            print(f"  - {error}")
    return 1


def _imprimir_json(
    comando: str, exito: bool, errores: list[str], resultado: dict[str, Any] | None
) -> None:
    """Salida JSON común de los comandos del ciclo de vida (ADR-0008, punto 26)."""
    datos = {
        "comando": comando,
        "exito": exito,
        "errores": errores,
        "version_agente": version("agentresearch"),
        "resultado": resultado,
    }
    # ASCII escapado: JSON válido aunque la consola no use UTF-8.
    print(json.dumps(datos, ensure_ascii=True, indent=2))


def _resumen(errores: int, advertencias: int) -> str:
    if errores == 0 and advertencias == 0:
        return "sin errores ni advertencias"
    texto_errores = f"{errores} error" + ("" if errores == 1 else "es")
    texto_advertencias = f"{advertencias} advertencia" + ("" if advertencias == 1 else "s")
    return f"{texto_errores}, {texto_advertencias}"


def _tolerar_caracteres_no_representables() -> None:
    """Evita que un carácter fuera de la codificación de la consola rompa la salida."""
    for flujo in (sys.stdout, sys.stderr):
        if isinstance(flujo, io.TextIOWrapper):
            flujo.reconfigure(errors="backslashreplace")


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

    if argumentos.comando == "protocolo" and argumentos.subcomando == "aprobar":
        sys.exit(
            ejecutar_protocolo_aprobar(
                argumentos.ruta,
                argumentos.aprobado_por,
                argumentos.justificaciones,
                argumentos.como_json,
            )
        )

    if argumentos.comando == "protocolo" and argumentos.subcomando == "enmendar":
        sys.exit(
            ejecutar_protocolo_enmendar(
                argumentos.ruta,
                argumentos.nivel,
                argumentos.enmendado_por,
                argumentos.justificacion,
                argumentos.efecto_esperado,
                argumentos.archivo_enmienda,
                argumentos.simular,
                argumentos.como_json,
            )
        )

    if argumentos.comando == "protocolo" and argumentos.subcomando == "historial":
        sys.exit(ejecutar_protocolo_historial(argumentos.ruta, argumentos.como_json))

    if argumentos.comando == "protocolo" and argumentos.subcomando == "decision":
        if argumentos.accion == "registrar":
            sys.exit(
                ejecutar_decision_registrar(
                    argumentos.archivo, argumentos.protocolo, argumentos.como_json
                )
            )
        sys.exit(
            ejecutar_decision_confirmar(
                argumentos.confirmado_por, argumentos.protocolo, argumentos.como_json
            )
        )


if __name__ == "__main__":
    main()
