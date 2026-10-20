"""Esquema del evento `busqueda_registrada` (ADR-0010, punto 16; especificación 2c).

Vive junto a los demás eventos del registro del estudio (`protocolo/eventos.jsonl`).
Se valida con pydantic estricto al leer el registro: la regla P-E10 reporta un evento
mal formado, números de importación no consecutivos o archivos de `importaciones/`
ausentes o alterados.
"""

import re
from typing import Literal

from pydantic import Field, model_validator

from agentresearch.protocolo.eventos import (
    HashSha256,
    IdEvento,
    ModeloEvento,
    PersonaHumana,
    RutaRelativa,
    TextoNoVacio,
    VersionProtocolo,
)

TIPO_BUSQUEDA_REGISTRADA = "busqueda_registrada"

_PATRON_ID_IMPORTACION = re.compile(r"imp-[0-9]{4}")
_PATRON_FECHA_HORA = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?([+-][0-9]{2}:[0-9]{2}|Z)"
)

FormatoImportacion = Literal["ris", "bibtex", "scopus_csv", "wos_txt", "csv"]
RelacionEcuacion = Literal["identica", "desviacion", "adaptacion_generica"]
OrigenEcuacionEsperada = Literal["ecuaciones_md", "regenerada"]
MotivoSoloLocal = Literal["sin_habilitar", "base_incompleta", "nunca_publicable"]

CARPETA_IMPORTACIONES = "importaciones"
CARPETA_ORIGINALES = "exportaciones_originales"
NOMBRES_ARCHIVOS_IMPORTACION = ("importacion.json", "registros.jsonl", "registros.csv")


def id_importacion_valido(texto: str) -> bool:
    """Indica si `texto` tiene la forma `imp-NNNN`."""
    return _PATRON_ID_IMPORTACION.fullmatch(texto) is not None


class EcuacionEsperada(ModeloEvento):
    """La ecuación que el protocolo vigente en la fecha de la búsqueda prescribe."""

    texto: TextoNoVacio
    hash: HashSha256
    origen: OrigenEcuacionEsperada
    version_agente: TextoNoVacio


class EcuacionEjecutada(ModeloEvento):
    """El texto que el investigador ejecutó en la interfaz de la base."""

    texto: TextoNoVacio
    hash: HashSha256


class ArchivoBusqueda(ModeloEvento):
    """Un archivo exportado de la búsqueda; `copia` es la ruta de su copia local."""

    nombre_original: TextoNoVacio
    formato: FormatoImportacion
    hash: HashSha256
    registros: int = Field(ge=0)
    copia: RutaRelativa


class PoliticaRegistrada(ModeloEvento):
    version: int = Field(ge=1)
    hash: HashSha256


class ConfiguracionRegistrada(ModeloEvento):
    hash: HashSha256


class CampoSoloLocal(ModeloEvento):
    campo: TextoNoVacio
    motivo: MotivoSoloLocal


class DatosBusquedaRegistrada(ModeloEvento):
    """Datos del evento `busqueda_registrada`."""

    id_importacion: TextoNoVacio
    fuente: TextoNoVacio
    plataforma: TextoNoVacio
    institucion_acceso: TextoNoVacio
    cobertura: TextoNoVacio
    lematizacion: str | None
    filtros: list[TextoNoVacio]
    fecha_hora_busqueda: TextoNoVacio
    fecha_hora_busqueda_utc: TextoNoVacio
    version_protocolo: VersionProtocolo
    evento_version: IdEvento
    ecuacion_esperada: EcuacionEsperada
    ecuacion_ejecutada: EcuacionEjecutada
    relacion_ecuacion: RelacionEcuacion
    justificacion_ecuacion: str
    resultados_interfaz: int = Field(ge=0)
    registros_leidos: int = Field(ge=0)
    justificacion_diferencia: str
    archivos: list[ArchivoBusqueda] = Field(min_length=1)
    mapeo: HashSha256 | None
    carpeta: RutaRelativa
    hash_importacion_json: HashSha256
    hash_registros_jsonl: HashSha256
    hash_registros_csv: HashSha256
    politica: PoliticaRegistrada
    configuracion_publicacion: ConfiguracionRegistrada
    version_normalizacion: int = Field(ge=1)
    campos_versionados: list[TextoNoVacio]
    campos_solo_locales: list[CampoSoloLocal]
    registrado_por: PersonaHumana

    @model_validator(mode="after")
    def _coherente(self) -> "DatosBusquedaRegistrada":
        if not id_importacion_valido(self.id_importacion):
            raise ValueError("`id_importacion` debe tener la forma `imp-NNNN`")
        if self.carpeta != f"{CARPETA_IMPORTACIONES}/{self.id_importacion}":
            raise ValueError(f"`carpeta` debe ser {CARPETA_IMPORTACIONES}/{self.id_importacion}")
        for campo in ("fecha_hora_busqueda", "fecha_hora_busqueda_utc"):
            if _PATRON_FECHA_HORA.fullmatch(getattr(self, campo)) is None:
                raise ValueError(f"`{campo}` debe ser una fecha y hora ISO 8601 con desfase")
        prefijo = f"{CARPETA_ORIGINALES}/{self.id_importacion}/"
        if any(not a.copia.startswith(prefijo) for a in self.archivos):
            raise ValueError(f"las copias de los originales van en {prefijo}")
        if self.registros_leidos != sum(a.registros for a in self.archivos):
            raise ValueError("`registros_leidos` no coincide con la suma de los archivos")
        if self.relacion_ecuacion == "desviacion" and not self.justificacion_ecuacion.strip():
            raise ValueError("una desviación de la ecuación lleva justificación")
        if (
            self.registros_leidos != self.resultados_interfaz
            and not self.justificacion_diferencia.strip()
        ):
            raise ValueError("una diferencia con los resultados de la interfaz lleva justificación")
        return self
