"""Confirmación interactiva: una barrera de procedimiento (ADR-0008, punto 11).

`aprobar`, `enmendar` y `decision confirmar` exigen que la entrada estándar sea
una consola, y piden al investigador escribir una frase exacta. Hoy las
herramientas con que Claude Code ejecuta comandos no ofrecen una consola (la
entrada es una tubería o el dispositivo nulo), así que el LLM no completa la
confirmación por su ruta normal. No es una garantía: se puede eludir
emulando una terminal. Su valor es de procedimiento, y cada confirmación deja
registrado quién la hizo.

En Windows, `isatty()` no basta, porque devuelve verdadero para el dispositivo
`NUL`; se usa `GetConsoleMode`, que solo tiene éxito con una consola real.
"""

import os
import sys
from typing import Protocol, TextIO

MENSAJE_SIN_TERMINAL = (
    "este comando exige una terminal interactiva: ejecútelo en su propia terminal "
    "(PowerShell, cmd, Windows Terminal, la terminal de VS Code, o una terminal de Linux o "
    "macOS). En Windows, Git Bash abierto como aplicación independiente (mintty) no ofrece "
    "una consola: use PowerShell o la terminal de VS Code. El LLM propone; el investigador "
    "decide (CLAUDE.md, regla 1)"
)


class Terminal(Protocol):
    """Diálogo con el investigador. Las pruebas inyectan una terminal simulada."""

    def es_interactiva(self) -> bool:
        """Indica si hay una persona al otro lado (la entrada estándar es una consola)."""
        ...

    def mostrar(self, texto: str) -> None:
        """Muestra un texto al investigador."""
        ...

    def preguntar(self, pregunta: str) -> str | None:
        """Hace una pregunta y devuelve la respuesta, o `None` si la entrada terminó."""
        ...


def es_consola_interactiva(flujo: TextIO) -> bool:
    """Indica si `flujo` es una consola interactiva, y no una tubería, un archivo o `NUL`."""
    try:
        descriptor = flujo.fileno()
    except (AttributeError, OSError, ValueError):
        return False
    if sys.platform == "win32":
        return _es_consola_de_windows(descriptor)
    return os.isatty(descriptor)


def _es_consola_de_windows(descriptor: int) -> bool:
    if sys.platform != "win32":  # para mypy en otros sistemas: msvcrt solo existe en Windows
        return False
    import ctypes
    import msvcrt
    from ctypes import wintypes

    try:
        manejador = msvcrt.get_osfhandle(descriptor)
    except OSError:
        return False
    modo = wintypes.DWORD()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return bool(kernel32.GetConsoleMode(wintypes.HANDLE(manejador), ctypes.byref(modo)))


class TerminalDelSistema:
    """Terminal real: lee de la entrada estándar y escribe en la salida de errores.

    El diálogo va a la salida de errores para que la salida estándar quede
    limpia cuando se pide `--json`.
    """

    def es_interactiva(self) -> bool:
        return es_consola_interactiva(sys.stdin)

    def mostrar(self, texto: str) -> None:
        print(texto, file=sys.stderr, flush=True)

    def preguntar(self, pregunta: str) -> str | None:
        sys.stderr.write(pregunta)
        sys.stderr.flush()
        linea = sys.stdin.readline()
        if not linea:
            return None
        return linea.rstrip("\r\n")
