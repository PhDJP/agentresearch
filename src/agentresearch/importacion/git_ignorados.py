"""Comprobación de que un original no quedará versionado (I-E10; ADR-0010, puntos 7 y 8).

Es la única excepción al principio de no depender de Git: solo `importar
registrar` la usa. `git check-ignore -q` sale con 0 si la ruta se ignora, con 1
si no y con 128 ante un error fatal; por defecto un archivo ya agregado al
índice no cuenta como ignorado. Solo se acepta la salida 0.
"""

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

ComprobadorDeIgnorados = Callable[[Path, Sequence[Path]], list[str]]
"""Recibe la raíz del estudio y las rutas; devuelve un mensaje por cada ruta que no se ignora."""

_ARREGLO = (
    "ejecute `agentresearch estudio actualizar` para recibir el `.gitignore` nuevo, o mueva "
    "el archivo fuera del estudio"
)


def comprobar_con_git(raiz: Path, rutas: Sequence[Path]) -> list[str]:
    """Ejecuta `git check-ignore -q` sobre cada ruta; devuelve los problemas encontrados."""
    problemas: list[str] = []
    for ruta in rutas:
        try:
            resultado = subprocess.run(
                ["git", "check-ignore", "-q", "--", str(ruta)],
                cwd=raiz,
                capture_output=True,
                check=False,
                timeout=60,
            )
        except FileNotFoundError:
            return [
                "Git no está instalado, y hace falta para comprobar que los originales no se "
                "versionan; instálelo o ejecute este comando en un equipo con Git"
            ]
        except subprocess.TimeoutExpired:
            return [f"`git check-ignore` no respondió para {_nombre(raiz, ruta)}"]
        if resultado.returncode == 0:
            continue
        nombre = _nombre(raiz, ruta)
        if resultado.returncode == 1:
            problemas.append(f"{nombre} no está ignorado por Git y quedaría versionado: {_ARREGLO}")
        else:
            problemas.append(
                f"no se pudo comprobar con Git si {nombre} se ignora (¿el estudio no es un "
                f"repositorio?): {_ARREGLO}"
            )
    return problemas


def _nombre(raiz: Path, ruta: Path) -> str:
    try:
        return ruta.relative_to(raiz).as_posix()
    except ValueError:
        return ruta.name
