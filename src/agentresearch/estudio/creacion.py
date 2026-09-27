"""Creación del repositorio de un estudio: `agentresearch nuevo-estudio` (ADR-0007).

Crea, desde las plantillas del paquete, los archivos del estudio: metadatos,
proyecto uv fijado a la versión exacta del agente, protocolo en borrador,
instrucciones del agente (`CLAUDE.md`, `.claude/settings.json` y la *skill*
`/protocolo`), `.gitignore`, `.gitattributes` y `README.md`. Registra el
evento `estudio_creado` con el hash de cada archivo, y escribe el anclaje.

Todo se arma en un directorio temporal junto al destino, que se renombra al
final: si algo falla, no queda un estudio a medias. No ejecuta Git ni uv, ni
usa la red: los pasos siguientes se muestran al investigador.
"""

import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from agentresearch.estudio.modelo import (
    LICENCIA_DATOS,
    NOMBRE_ARCHIVO,
    VERSION_ESQUEMA_ESTUDIO,
    Agente,
    Estudio,
    texto_estudio,
)
from agentresearch.protocolo.archivo import (
    actualizar_documento,
    cargar_protocolo,
    texto_plantilla,
    texto_protocolo,
)
from agentresearch.protocolo.ciclo_de_vida import escribir_anclaje
from agentresearch.protocolo.decisiones import es_identificador_exacto_de_modelo
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import (
    TIPO_ESTUDIO_CREADO,
    ArchivoRegistrado,
    DatosEstudioCreado,
)
from agentresearch.protocolo.instrucciones import hashes_de_instrucciones
from agentresearch.trazabilidad import (
    Anclaje,
    EventoRegistro,
    RegistroEncadenado,
    escribir_atomico,
    hash_archivo,
)

URL_REPOSITORIO_AGENTE = "https://github.com/PhDJP/agentresearch"
RUTA_PROTOCOLO = "protocolo/protocolo.yaml"
DIRECTORIO_INSUMOS = "protocolo/insumos"

PLANTILLAS: dict[str, str] = {
    "CLAUDE.md": "CLAUDE.md",
    "README.md": "README.md",
    "pyproject.toml": "pyproject.toml",
    "gitignore": ".gitignore",
    "gitattributes": ".gitattributes",
    "claude/settings.json": ".claude/settings.json",
    "claude/skills/protocolo/SKILL.md": ".claude/skills/protocolo/SKILL.md",
    "claude/skills/protocolo/secciones.md": ".claude/skills/protocolo/secciones.md",
    "claude/skills/protocolo/formatos.md": ".claude/skills/protocolo/formatos.md",
}
"""Plantilla del paquete (en `agentresearch/estudio/plantillas/`) y su ruta en el estudio."""

_MARCADOR = re.compile(r"\{\{([a-z_]+)\}\}")
_NOMBRE_VALIDO = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")

Reloj = Callable[[], datetime]


class ErrorCreacion(Exception):
    """El estudio no se puede crear; `errores` explica por qué, sin haber escrito nada."""

    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("; ".join(errores))


@dataclass(frozen=True, slots=True)
class ResultadoCreacion:
    """Un estudio recién creado."""

    ruta: Path
    estudio: Estudio
    evento: EventoRegistro
    anclaje: Anclaje
    archivos: list[str] = field(default_factory=list)
    """Rutas relativas de todos los archivos creados, ordenadas."""

    def pasos_siguientes(self) -> list[str]:
        """Lo que hace el investigador después: instalar, versionar y abrir Claude Code."""
        nombre = self.estudio.nombre
        return [
            f'cd "{self.ruta}"',
            f"uv sync   (instala agentresearch {self.estudio.agente.version} y crea uv.lock)",
            "git init",
            "git add -A",
            f'git commit -m "Crear el estudio (anclaje {self.anclaje})"',
            f"gh repo create {nombre} --private --source . --push   (privado hasta registrar "
            "el protocolo)",
            "Abra Claude Code en la carpeta, acepte el diálogo de confianza del proyecto (activa "
            "los permisos de .claude/settings.json) y escriba /protocolo",
        ]

    def como_dict(self) -> dict[str, Any]:
        return {
            "ruta": str(self.ruta),
            "estudio": self.estudio.model_dump(mode="json"),
            "evento": self.evento.id,
            "tipo_evento": self.evento.tipo,
            "anclaje": str(self.anclaje),
            "archivos": self.archivos,
            "pasos_siguientes": self.pasos_siguientes(),
        }


def fuente_del_agente(version_agente: str) -> str:
    """Especificación de instalación del agente fijada a la etiqueta de su versión."""
    return f"git+{URL_REPOSITORIO_AGENTE}@v{version_agente}"


def crear_estudio(
    ruta: Path | str,
    titulo: str,
    modelo: str,
    contexto: Path | str | None = None,
    reloj: Reloj | None = None,
) -> ResultadoCreacion:
    """Crea el repositorio de un estudio en `ruta`, que no debe existir o debe estar vacío.

    Lanza `ErrorCreacion`, sin escribir nada, si algún argumento no es válido.
    """
    destino = Path(ruta).resolve()
    titulo = titulo.strip()
    contexto_ruta = Path(contexto) if contexto is not None else None
    _exigir_argumentos_validos(destino, titulo, modelo, contexto_ruta)

    momento = (reloj or _ahora)()
    version_agente = version("agentresearch")
    estudio = Estudio(
        version_esquema=VERSION_ESQUEMA_ESTUDIO,
        nombre=destino.name.lower(),
        titulo=titulo,
        fecha_creacion=momento.astimezone(UTC).date().isoformat(),
        agente=Agente(version=version_agente, fuente=fuente_del_agente(version_agente)),
        modelo=modelo,
        licencia_datos=LICENCIA_DATOS,
    )
    temporal = Path(tempfile.mkdtemp(dir=destino.parent, prefix=f".{destino.name}.", suffix=".tmp"))
    try:
        evento, anclaje = _escribir_estudio(temporal, estudio, contexto_ruta, momento)
        archivos = _archivos_relativos(temporal)
        if destino.exists():
            destino.rmdir()  # existe vacío: se reemplaza por el estudio completo
        os.replace(temporal, destino)
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise
    return ResultadoCreacion(destino, estudio, evento, anclaje, archivos)


def _ahora() -> datetime:
    return datetime.now(UTC)


def _exigir_argumentos_validos(
    destino: Path, titulo: str, modelo: str, contexto: Path | None
) -> None:
    errores = []
    if destino.exists() and (not destino.is_dir() or any(destino.iterdir())):
        errores.append(f"{destino} ya existe y no es un directorio vacío")
    elif not destino.parent.is_dir():
        errores.append(f"no existe el directorio {destino.parent}")
    if not _NOMBRE_VALIDO.match(destino.name.lower()):
        errores.append(
            f"el nombre de la carpeta, {destino.name!r}, será el nombre del estudio y del "
            "proyecto uv: use solo letras sin tilde, dígitos, puntos, guiones y guiones bajos, "
            "empezando y terminando con letra o dígito (p. ej. mapeo-mucilago-cafe)"
        )
    if not titulo or any(caracter in titulo for caracter in "\r\n\t"):
        errores.append("el título no puede estar vacío ni tener saltos de línea")
    if not es_identificador_exacto_de_modelo(modelo):
        errores.append(
            f"--modelo {modelo!r} no es un identificador exacto: sin espacios, con su versión "
            "y sin alias como «opus» o «-latest» (p. ej. claude-opus-5-5)"
        )
    if contexto is not None and not contexto.is_file():
        errores.append(f"--contexto: no existe el archivo {contexto}")
    if errores:
        raise ErrorCreacion(errores)


def _escribir_estudio(
    raiz: Path, estudio: Estudio, contexto: Path | None, momento: datetime
) -> tuple[EventoRegistro, Anclaje]:
    valores = {
        "titulo": estudio.titulo,
        "nombre": estudio.nombre,
        "modelo": estudio.modelo,
        "version_agente": estudio.agente.version,
        "fuente_agente": estudio.agente.fuente,
        "fecha": estudio.fecha_creacion,
    }
    for origen, destino in PLANTILLAS.items():
        _escribir(raiz, destino, renderizar(texto_de_plantilla(origen), valores))
    _escribir(raiz, NOMBRE_ARCHIVO, texto_estudio(estudio))

    documento = cargar_protocolo(texto_plantilla())
    metadatos = documento.protocolo.metadatos.model_copy(update={"titulo": estudio.titulo})
    actualizar_documento(documento, documento.protocolo.model_copy(update={"metadatos": metadatos}))
    _escribir(raiz, RUTA_PROTOCOLO, texto_protocolo(documento))

    insumos = []
    if contexto is not None:
        relativa = f"{DIRECTORIO_INSUMOS}/{contexto.name}"
        copia = raiz.joinpath(*relativa.split("/"))
        escribir_atomico(copia, contexto.read_bytes())
        insumos.append(ArchivoRegistrado(ruta=relativa, hash=hash_archivo(copia)))

    instrucciones = hashes_de_instrucciones(raiz)
    otros = [NOMBRE_ARCHIVO, RUTA_PROTOCOLO] + [
        destino for destino in PLANTILLAS.values() if destino not in instrucciones
    ]
    datos = DatosEstudioCreado(
        nombre=estudio.nombre,
        titulo=estudio.titulo,
        modelo=estudio.modelo,
        fuente_agente=estudio.agente.fuente,
        archivos=[
            ArchivoRegistrado(ruta=ruta, hash=hash_archivo(raiz.joinpath(*ruta.split("/"))))
            for ruta in sorted(otros)
        ],
        instrucciones=[
            ArchivoRegistrado(ruta=ruta, hash=hash_) for ruta, hash_ in instrucciones.items()
        ],
        insumos=insumos,
    )
    rutas = RutasProtocolo.desde(raiz.joinpath(*RUTA_PROTOCOLO.split("/")))
    evento = RegistroEncadenado(rutas.eventos, reloj=lambda: momento).agregar(
        TIPO_ESTUDIO_CREADO, datos.model_dump(mode="json")
    )
    return evento, escribir_anclaje(rutas)


def texto_de_plantilla(nombre: str) -> str:
    """Texto de una plantilla del estudio incluida en el paquete."""
    recurso = files("agentresearch.estudio").joinpath("plantillas", *nombre.split("/"))
    return recurso.read_bytes().decode("utf-8")


def renderizar(texto: str, valores: dict[str, str]) -> str:
    """Reemplaza cada `{{clave}}` por su valor. Una clave desconocida es un error del paquete."""

    def _valor(coincidencia: re.Match[str]) -> str:
        clave = coincidencia.group(1)
        if clave not in valores:
            raise KeyError(f"marcador desconocido en una plantilla del estudio: {clave}")
        return valores[clave]

    return _MARCADOR.sub(_valor, texto)


def _escribir(raiz: Path, relativa: str, texto: str) -> None:
    escribir_atomico(raiz.joinpath(*relativa.split("/")), texto.encode("utf-8"))


def _archivos_relativos(raiz: Path) -> list[str]:
    return sorted(
        PurePosixPath(*archivo.relative_to(raiz).parts).as_posix()
        for archivo in raiz.rglob("*")
        if archivo.is_file()
    )
