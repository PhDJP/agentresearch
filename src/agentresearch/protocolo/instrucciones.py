"""Instrucciones del agente en un estudio: si cambiaron desde su registro (ADR-0007).

Las instrucciones son los archivos que gobiernan a Claude Code en el
repositorio del estudio: `CLAUDE.md`, `.claude/settings.json` (modelo fijado
y permisos) y las *skills* de `.claude/skills/`. `nuevo-estudio` registra su
hash en el evento `estudio_creado`. `validar` e `historial` los comparan con
los archivos actuales y, si difieren, muestran una nota de estado
("instrucciones del agente modificadas"). No es un error ni una advertencia:
el protocolo sigue siendo válido, pero el reporte debe poder decir con qué
instrucciones trabajó el agente.

`.claude/settings.local.json` no cuenta: es la configuración local de cada
persona y no se versiona.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from agentresearch.protocolo.ciclo_de_vida import EstadoRegistro
from agentresearch.trazabilidad import hash_archivo

RUTA_CLAUDE_MD = "CLAUDE.md"
RUTA_CONFIGURACION = ".claude/settings.json"
DIRECTORIO_SKILLS = ".claude/skills"


def rutas_de_instrucciones(estudio: Path) -> list[str]:
    """Rutas relativas (con `/`) de los archivos de instrucciones que existen en el estudio."""
    rutas = [ruta for ruta in (RUTA_CLAUDE_MD, RUTA_CONFIGURACION) if (estudio / ruta).is_file()]
    skills = estudio.joinpath(*DIRECTORIO_SKILLS.split("/"))
    if skills.is_dir():
        rutas += [
            PurePosixPath(*archivo.relative_to(estudio).parts).as_posix()
            for archivo in skills.rglob("*")
            if archivo.is_file()
        ]
    return sorted(rutas)


def hashes_de_instrucciones(estudio: Path) -> dict[str, str]:
    """Hash de cada archivo de instrucciones del estudio, por su ruta relativa."""
    return {
        ruta: hash_archivo(estudio.joinpath(*ruta.split("/")))
        for ruta in rutas_de_instrucciones(estudio)
    }


@dataclass(frozen=True, slots=True)
class EstadoInstrucciones:
    """Diferencias entre las instrucciones registradas y los archivos actuales."""

    evento: str
    """Evento que registró las instrucciones con que se comparan."""
    modificados: list[str]
    eliminados: list[str]
    agregados: list[str]

    @property
    def modificadas(self) -> bool:
        return bool(self.modificados or self.eliminados or self.agregados)

    def nota(self) -> str | None:
        """Nota de estado para `validar` e `historial`, o `None` si nada cambió."""
        if not self.modificadas:
            return None
        partes = []
        if self.modificados:
            partes.append(f"cambiaron {', '.join(self.modificados)}")
        if self.eliminados:
            partes.append(f"faltan {', '.join(self.eliminados)}")
        if self.agregados:
            partes.append(f"no estaban registrados {', '.join(self.agregados)}")
        return (
            f"instrucciones del agente modificadas desde su registro en {self.evento}: "
            f"{'; '.join(partes)}. Si el cambio no fue deliberado, restáurelo con Git; si lo "
            "fue, el reporte debe declararlo (un comando para registrar la actualización está "
            "previsto en la hoja de ruta)"
        )

    def como_dict(self) -> dict[str, Any]:
        return {
            "evento_registro": self.evento,
            "modificadas": self.modificadas,
            "modificados": self.modificados,
            "eliminados": self.eliminados,
            "agregados": self.agregados,
        }


def estado_instrucciones(registro: EstadoRegistro) -> EstadoInstrucciones | None:
    """Compara las instrucciones registradas al crear el estudio con las actuales.

    Devuelve `None` si el registro no tiene el evento `estudio_creado` (por
    ejemplo, un protocolo que no se creó con `nuevo-estudio`).
    """
    creacion = registro.creacion
    if creacion is None:
        return None
    registradas = {archivo.ruta: archivo.hash for archivo in creacion.datos.instrucciones}
    actuales = hashes_de_instrucciones(registro.rutas.estudio)
    return EstadoInstrucciones(
        evento=creacion.evento.id,
        modificados=sorted(
            ruta
            for ruta, hash_registrado in registradas.items()
            if ruta in actuales and actuales[ruta] != hash_registrado
        ),
        eliminados=sorted(ruta for ruta in registradas if ruta not in actuales),
        agregados=sorted(ruta for ruta in actuales if ruta not in registradas),
    )
