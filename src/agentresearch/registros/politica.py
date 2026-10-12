"""Política de datos de terceros: la del paquete y la configuración de publicación del estudio.

Principio del ADR-0010: **local completo, nube mínima y configurable**. Todo se
importa y se conserva completo en local; lo que se versiona lo decide cada
estudio en su `publicacion_datos.yaml`, con la base registrada de cada campo.

- `politica_datos.yaml` (en este paquete): los campos `nunca_publicables` y, por
  fuente, el techo de lo que un estudio puede habilitar.
- `publicacion_datos.yaml` (en el estudio): por fuente, los campos que el
  estudio habilita y la base de cada uno; el permiso de la evidencia literal y
  el del respaldo en la nube.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, ValidationInfo, field_validator, model_validator
from pydantic_core import ErrorDetails
from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError

from agentresearch.protocolo.archivo import describir_error_de_esquema, formatear_ubicacion
from agentresearch.registros.modelo import ModeloRegistros
from agentresearch.trazabilidad import hash_archivo, hash_bytes

NOMBRE_POLITICA = "politica_datos.yaml"
"""Archivo de la política dentro del paquete `agentresearch.registros`."""

CAMPOS_HABILITABLES: tuple[str, ...] = (
    "id_fuente",
    "titulo",
    "autores",
    "anio",
    "fuente_publicacion",
    "volumen",
    "numero",
    "paginas",
    "doi",
    "pmid",
    "tipo_documento",
    "idioma",
)
"""Campos del registro que un estudio puede habilitar, en el orden del esquema.

`tipo_id_fuente` se versiona junto con `id_fuente`. Los demás campos se
versionan siempre (procedencia y hash) o nunca (`resumen`, palabras clave y
`otros`).
"""

NUNCA_PUBLICABLES_MINIMOS = frozenset(
    {
        "resumen",
        "palabras_clave_autor",
        "palabras_clave_indexadas",
        "referencias",
        "conteos_citas",
        "afiliaciones",
        "financiacion",
    }
)
"""Lo que `nunca_publicables` de la política debe contener como mínimo (ADR-0010)."""

CAMPOS_DE_EVIDENCIA = ("resumen", "palabras_clave_autor", "palabras_clave_indexadas")
"""Campos de los que puede salir una cita de evidencia literal (ADR-0010, punto 5)."""

EstadoPermiso = Literal["sin_verificar", "permitido", "no_permitido"]
CampoDeEvidencia = Literal["resumen", "palabras_clave_autor", "palabras_clave_indexadas"]
TipoBase = Literal["institucion", "revista", "licencia"]

_PATRON_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_PREFIJO_VALOR = "Value error, "


# ----------------------------------------------------------------- errores


@dataclass(frozen=True, slots=True)
class ProblemaConfiguracion:
    """Un problema de la configuración de publicación (regla I-E13 del registro).

    `linea` y `columna` empiezan en 1 y son `None` si no se pueden determinar.
    """

    mensaje: str
    ubicacion: str | None = None
    linea: int | None = None
    columna: int | None = None

    def __str__(self) -> str:
        return f"{self.ubicacion}: {self.mensaje}" if self.ubicacion else self.mensaje


class ErrorConfiguracionPublicacion(Exception):
    """El archivo no existe, no es legible o no cumple el esquema ni la política.

    `problemas` los trae todos a la vez.
    """

    def __init__(self, problemas: list[ProblemaConfiguracion]) -> None:
        self.problemas = problemas
        super().__init__("; ".join(str(problema) for problema in problemas))


class ErrorPoliticaDatos(Exception):
    """La política del paquete no es válida (un defecto del agente, no del estudio)."""


# -------------------------------------------------------- política del paquete


class PoliticaFuente(ModeloRegistros):
    """Lo que una fuente puede aportar y que un estudio puede habilitar (el techo)."""

    campos_habilitables: list[str]

    @field_validator("campos_habilitables")
    @classmethod
    def _validar_campos(cls, valor: list[str]) -> list[str]:
        if len(set(valor)) != len(valor):
            raise ValueError("hay campos repetidos")
        invalidos = [campo for campo in valor if campo not in CAMPOS_HABILITABLES]
        if invalidos:
            raise ValueError(f"no son campos habilitables del registro: {', '.join(invalidos)}")
        return valor


class PoliticaDatos(ModeloRegistros):
    """La política del paquete (`politica_datos.yaml`)."""

    version: int = Field(ge=1)
    nunca_publicables: list[str]
    fuentes: dict[str, PoliticaFuente]

    @field_validator("nunca_publicables")
    @classmethod
    def _validar_nunca_publicables(cls, valor: list[str]) -> list[str]:
        faltan = NUNCA_PUBLICABLES_MINIMOS - set(valor)
        if faltan:
            raise ValueError(f"faltan campos que nunca se publican: {', '.join(sorted(faltan))}")
        return valor


def leer_bytes_politica() -> bytes:
    """Lee los bytes de la política del paquete con `importlib.resources`.

    Se lee como recurso del paquete y no con una ruta del repositorio, para que
    funcione en el paquete instalado.
    """
    recurso = files("agentresearch.registros").joinpath(NOMBRE_POLITICA)
    return recurso.read_bytes()


def hash_politica() -> str:
    """SHA-256 de los bytes de la política del paquete, que registra cada importación."""
    return hash_bytes(leer_bytes_politica())


def cargar_politica(contenido: bytes | None = None) -> PoliticaDatos:
    """Carga y valida la política del paquete (o los bytes que se pasen, para pruebas).

    Lanza `ErrorPoliticaDatos` si no es UTF-8, no es YAML válido o no cumple el
    esquema.
    """
    contenido = leer_bytes_politica() if contenido is None else contenido
    datos, problema = _analizar_yaml(contenido)
    if problema is not None:
        raise ErrorPoliticaDatos(f"{NOMBRE_POLITICA}: {problema}")
    try:
        politica = PoliticaDatos.model_validate(datos)
    except ValidationError as error:
        problemas = "; ".join(str(_problema_de_esquema(detalle)) for detalle in error.errors())
        raise ErrorPoliticaDatos(f"{NOMBRE_POLITICA}: {problemas}") from None
    comunes = [
        campo
        for fuente in politica.fuentes.values()
        for campo in fuente.campos_habilitables
        if campo in politica.nunca_publicables
    ]
    if comunes:
        raise ErrorPoliticaDatos(
            f"{NOMBRE_POLITICA}: un campo no puede ser habilitable y nunca publicable: "
            + ", ".join(sorted(set(comunes)))
        )
    return politica


# --------------------------------------------------- configuración del estudio


class Base(ModeloRegistros):
    """La base de la habilitación de un campo (ADR-0010, punto 4).

    Dice quién lo confirmó: la institución, la política de la revista o
    editorial, o la licencia de los datos (un término de contrato es una
    licencia).
    """

    tipo: TipoBase | None = None
    detalle: str | None = None
    medio: str | None = None
    fecha: str | None = None

    @field_validator("tipo", "detalle", "medio", "fecha", mode="before")
    @classmethod
    def _vacio_es_nulo(cls, valor: Any) -> Any:
        # YAML interpreta `2026-10-05` sin comillas como fecha, no como texto.
        if isinstance(valor, datetime):
            return valor
        if isinstance(valor, date):
            return valor.isoformat()
        if isinstance(valor, str):
            return valor.strip() or None
        return valor

    @field_validator("fecha")
    @classmethod
    def _validar_fecha(cls, valor: str | None, info: ValidationInfo) -> str | None:
        if valor is None:
            return None
        if _PATRON_FECHA.fullmatch(valor) is None:
            raise ValueError("la fecha debe tener la forma AAAA-MM-DD")
        try:
            dia = date.fromisoformat(valor)
        except ValueError:
            raise ValueError("la fecha no existe en el calendario") from None
        if dia > _ultimo_dia_admitido(info):
            raise ValueError("la fecha es futura")
        return valor

    @property
    def es_completa(self) -> bool:
        """`tipo`, `detalle` y `fecha` siempre; `medio` solo con `tipo: institucion`."""
        if not (self.tipo and self.detalle and self.fecha):
            return False
        return not (self.tipo == "institucion" and not self.medio)


def _ultimo_dia_admitido(info: ValidationInfo) -> date:
    """Último día que no es futuro: la fecha UTC del reloj más un día, por las zonas horarias."""
    contexto = info.context or {}
    ahora = contexto.get("ahora")
    if not isinstance(ahora, datetime):
        ahora = datetime.now(UTC)
    return ahora.astimezone(UTC).date() + timedelta(days=1)


class CampoConfigurado(ModeloRegistros):
    """Un campo que el estudio habilita para una fuente, con su base."""

    base: Base


class FuenteConfigurada(ModeloRegistros):
    """Los campos que el estudio habilita para una fuente."""

    campos: dict[str, CampoConfigurado] = Field(default_factory=dict)


class Permiso(ModeloRegistros):
    """Un permiso del estudio (evidencia literal o respaldo en la nube) con su base."""

    estado: EstadoPermiso
    base: Base | None = None

    @model_validator(mode="after")
    def _permitido_exige_base_completa(self) -> "Permiso":
        if self.estado == "permitido" and (self.base is None or not self.base.es_completa):
            raise ValueError("`permitido` exige una base completa (tipo, detalle y fecha)")
        return self


class ConfiguracionPublicacion(ModeloRegistros):
    """La configuración de publicación de un estudio (`publicacion_datos.yaml`).

    - `fuentes`: por fuente, los campos habilitados y su base.
    - `evidencia_literal`: por campo de origen, si el texto de una cita breve
      tomada de él puede versionarse. Lo ausente equivale a `no_permitido`.
    - `respaldo_nube`: por fuente, si la nube institucional es un lugar de
      respaldo permitido. Lo ausente equivale a `sin_verificar`.
    """

    fuentes: dict[str, FuenteConfigurada] = Field(default_factory=dict)
    evidencia_literal: dict[CampoDeEvidencia, Permiso] = Field(default_factory=dict)
    respaldo_nube: dict[str, Permiso] = Field(default_factory=dict)


def hash_configuracion(ruta: Path | str) -> str:
    """SHA-256 de los bytes de `publicacion_datos.yaml`, que registra cada importación."""
    return hash_archivo(Path(ruta))


def cargar_configuracion(
    ruta: Path | str,
    politica: PoliticaDatos | None = None,
    reloj: Callable[[], datetime] | None = None,
) -> ConfiguracionPublicacion:
    """Lee y valida `publicacion_datos.yaml`; lanza `ErrorConfiguracionPublicacion`."""
    ruta = Path(ruta)
    try:
        contenido = ruta.read_bytes()
    except FileNotFoundError:
        raise ErrorConfiguracionPublicacion(
            [ProblemaConfiguracion(f"el archivo no existe: {ruta}")]
        ) from None
    except OSError as error:
        raise ErrorConfiguracionPublicacion(
            [ProblemaConfiguracion(f"no se pudo leer el archivo {ruta}: {error.strerror}")]
        ) from None
    return decodificar_configuracion(contenido, politica, reloj)


def decodificar_configuracion(
    contenido: bytes,
    politica: PoliticaDatos | None = None,
    reloj: Callable[[], datetime] | None = None,
) -> ConfiguracionPublicacion:
    """Valida los bytes de una configuración; si hay problemas, los lanza todos a la vez.

    `reloj` devuelve la hora actual con zona horaria; sirve para validar que las
    fechas de las bases no sean futuras sin depender del reloj del sistema.
    """
    politica = politica if politica is not None else cargar_politica()
    ahora = _ahora(reloj)
    datos, problema = _analizar_yaml(contenido)
    if problema is not None:
        raise ErrorConfiguracionPublicacion([problema])
    if datos is None:
        raise ErrorConfiguracionPublicacion(
            [ProblemaConfiguracion("el archivo está vacío; debe ser un mapa con `fuentes`")]
        )
    if not isinstance(datos, dict):
        raise ErrorConfiguracionPublicacion(
            [ProblemaConfiguracion("la raíz del archivo debe ser un mapa de claves y valores")]
        )
    problemas = _problemas_de_politica(datos, politica)
    try:
        configuracion = ConfiguracionPublicacion.model_validate(datos, context={"ahora": ahora})
    except ValidationError as error:
        problemas = [_problema_de_esquema(detalle) for detalle in error.errors()] + problemas
    if problemas:
        raise ErrorConfiguracionPublicacion(problemas)
    return configuracion


def _ahora(reloj: Callable[[], datetime] | None) -> datetime:
    ahora = reloj() if reloj is not None else datetime.now(UTC)
    if ahora.tzinfo is None:
        raise ValueError("el reloj debe devolver una fecha con zona horaria")
    return ahora


def _problemas_de_politica(
    datos: Mapping[str, Any], politica: PoliticaDatos
) -> list[ProblemaConfiguracion]:
    """Revisa los campos de `fuentes` contra la política, sobre los datos sin validar.

    Se revisa sobre los datos crudos para informar estos problemas junto con los
    de esquema. Lo que no tenga la forma esperada lo informa el esquema.
    """
    problemas: list[ProblemaConfiguracion] = []
    fuentes = datos.get("fuentes")
    if not isinstance(fuentes, dict):
        return problemas
    for id_fuente, entrada in fuentes.items():
        campos = entrada.get("campos") if isinstance(entrada, dict) else None
        if not isinstance(campos, dict):
            continue
        techo = politica.fuentes.get(str(id_fuente))
        for nombre in campos:
            ubicacion = f"fuentes.{id_fuente}.campos.{nombre}"
            if nombre in politica.nunca_publicables:
                mensaje = "es un campo que nunca se publica; no se puede habilitar (ADR-0010)"
            elif nombre not in CAMPOS_HABILITABLES:
                mensaje = "no es un campo habilitable del registro"
            elif techo is not None and nombre not in techo.campos_habilitables:
                mensaje = f"la fuente `{id_fuente}` no aporta este campo (techo de la política)"
            else:
                continue
            problemas.append(ProblemaConfiguracion(mensaje, ubicacion))
    return problemas


# ------------------------------------------------------------- utilidades


def _yaml() -> YAML:
    analizador = YAML(typ="safe")
    analizador.allow_duplicate_keys = False
    return analizador


def _analizar_yaml(contenido: bytes) -> tuple[Any, ProblemaConfiguracion | None]:
    """Decodifica en UTF-8 y analiza YAML; devuelve `(datos, None)` o `(None, problema)`."""
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        return None, ProblemaConfiguracion("el archivo no está codificado en UTF-8")
    try:
        return _yaml().load(texto), None
    except YAMLError as error:
        marca = getattr(error, "problem_mark", None)
        linea = marca.line + 1 if marca is not None else None
        columna = marca.column + 1 if marca is not None else None
        if isinstance(error, DuplicateKeyError):
            mensaje = "clave repetida en un mapa"
        else:
            detalle = getattr(error, "problem", None)
            mensaje = f"YAML mal formado ({detalle})" if detalle else "YAML mal formado"
        return None, ProblemaConfiguracion(mensaje, linea=linea, columna=columna)


def _problema_de_esquema(detalle: ErrorDetails) -> ProblemaConfiguracion:
    ruta = [paso for paso in detalle["loc"] if isinstance(paso, str | int)]
    ubicacion = formatear_ubicacion(ruta) or None
    if detalle["type"] == "value_error":
        mensaje = str(detalle["msg"]).removeprefix(_PREFIJO_VALOR)
    else:
        sin_ubicacion: ErrorDetails = {**detalle, "loc": ()}
        mensaje = describir_error_de_esquema(sin_ubicacion)
    return ProblemaConfiguracion(mensaje, ubicacion)
