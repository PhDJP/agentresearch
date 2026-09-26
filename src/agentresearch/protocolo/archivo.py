"""Lectura y escritura del protocolo en YAML, conservando comentarios.

Se usa ruamel.yaml en modo de ida y vuelta (*round-trip*): el documento
original, con sus comentarios, comillas y estilo, se conserva en un
`CommentedMap`, y el modelo pydantic se valida a partir de una copia en tipos
simples de Python. Para escribir cambios, `actualizar_documento()` fusiona el
modelo sobre el documento original clave por clave (y las listas con `id`, por
su `id`), de modo que los comentarios de lo que no cambió se conservan.

Leer y volver a escribir un protocolo sin cambios produce un archivo idéntico
byte a byte, siempre que siga el formato de la plantilla (indentación de 2
espacios, guiones de lista con 2 espacios de sangría). Esto importa porque el
ciclo de vida del protocolo registra el hash del archivo.
"""

import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError
from ruamel.yaml.representer import RoundTripRepresenter
from ruamel.yaml.scalarbool import ScalarBoolean
from ruamel.yaml.scalarfloat import ScalarFloat
from ruamel.yaml.scalarint import ScalarInt
from ruamel.yaml.scalarstring import ScalarString

from agentresearch.protocolo.modelo import VERSION_ESQUEMA, Protocolo

ANCHO_DE_LINEA = 4096
"""Ancho máximo antes de partir una línea; grande para que los párrafos no se partan."""


class _Representador(RoundTripRepresenter):
    """Representa `None` como `null` explícito (ruamel lo escribiría vacío)."""


_Representador.add_representer(
    type(None),
    lambda representador, _dato: representador.represent_scalar("tag:yaml.org,2002:null", "null"),
)


def crear_yaml() -> YAML:
    """Crea un analizador YAML de ida y vuelta con el formato de la plantilla."""
    yaml = YAML(typ="rt")
    yaml.Representer = _Representador
    yaml.preserve_quotes = True
    yaml.width = ANCHO_DE_LINEA
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.allow_duplicate_keys = False
    return yaml


@dataclass(frozen=True, slots=True)
class ProblemaLectura:
    """Un problema que impide leer el protocolo o conformarlo al esquema (regla P-E00).

    `linea` y `columna` empiezan en 1 y son `None` si no se pueden determinar.
    """

    mensaje: str
    ubicacion: str | None = None
    linea: int | None = None
    columna: int | None = None


class ErrorLecturaProtocolo(Exception):
    """El archivo no es legible, no es YAML válido o no cumple el esquema."""

    def __init__(self, problemas: list[ProblemaLectura]) -> None:
        self.problemas = problemas
        super().__init__("; ".join(problema.mensaje for problema in problemas))


@dataclass(slots=True)
class DocumentoProtocolo:
    """Un protocolo leído: el YAML original con comentarios y su modelo validado."""

    datos: CommentedMap
    protocolo: Protocolo


def texto_plantilla() -> str:
    """Devuelve el texto de la plantilla comentada del protocolo."""
    recurso = files("agentresearch.protocolo").joinpath("plantillas", "protocolo.yaml")
    return recurso.read_bytes().decode("utf-8")


def leer_protocolo(ruta: Path | str) -> DocumentoProtocolo:
    """Lee y valida contra el esquema un archivo de protocolo.

    Lanza `ErrorLecturaProtocolo` si el archivo no existe, no es UTF-8, no es
    YAML válido o no cumple el esquema.
    """
    ruta = Path(ruta)
    try:
        contenido = ruta.read_bytes()
    except FileNotFoundError:
        raise ErrorLecturaProtocolo([ProblemaLectura(f"el archivo no existe: {ruta}")]) from None
    except OSError as error:
        raise ErrorLecturaProtocolo(
            [ProblemaLectura(f"no se pudo leer el archivo {ruta}: {error.strerror}")]
        ) from None
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        raise ErrorLecturaProtocolo(
            [ProblemaLectura("el archivo no está codificado en UTF-8")]
        ) from None
    return cargar_protocolo(texto)


def cargar_protocolo(texto: str) -> DocumentoProtocolo:
    """Analiza y valida contra el esquema el texto YAML de un protocolo."""
    datos = _analizar_yaml(texto)
    _verificar_version_esquema(datos)
    try:
        protocolo = Protocolo.model_validate(a_python(datos))
    except ValidationError as error:
        raise ErrorLecturaProtocolo(
            [_problema_de_esquema(detalle, datos) for detalle in error.errors()]
        ) from None
    return DocumentoProtocolo(datos=datos, protocolo=protocolo)


def texto_protocolo(documento: DocumentoProtocolo) -> str:
    """Serializa el documento a texto YAML, con fin de línea LF."""
    salida = io.StringIO()
    crear_yaml().dump(documento.datos, salida)
    return salida.getvalue()


def escribir_protocolo(documento: DocumentoProtocolo, ruta: Path | str) -> None:
    """Escribe el documento en `ruta`, en UTF-8 y con fin de línea LF."""
    with Path(ruta).open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(texto_protocolo(documento))


def actualizar_documento(documento: DocumentoProtocolo, protocolo: Protocolo) -> None:
    """Fusiona `protocolo` sobre el YAML del documento, conservando sus comentarios.

    Los mapas se fusionan clave por clave, las listas de elementos con `id` se
    fusionan por su `id` (no por posición) y las demás listas, posición por
    posición. Un texto que cambia conserva su estilo de comillas. Solo se
    escriben los campos presentes en el YAML de origen o asignados
    explícitamente en el modelo, no los valores por defecto implícitos.
    """
    nuevo = protocolo.model_dump(mode="python", exclude_unset=True)
    _fusionar_mapa(documento.datos, nuevo)
    documento.protocolo = protocolo


def a_python(valor: Any) -> Any:
    """Convierte los tipos de ruamel.yaml en tipos simples de Python."""
    if isinstance(valor, Mapping):
        return {a_python(clave): a_python(dato) for clave, dato in valor.items()}
    if isinstance(valor, list | tuple):
        return [a_python(elemento) for elemento in valor]
    if isinstance(valor, ScalarString):
        return str(valor)
    if isinstance(valor, ScalarBoolean):
        return bool(valor)
    if isinstance(valor, ScalarFloat):
        return float(valor)
    if isinstance(valor, ScalarInt):
        return int(valor)
    return valor


def _analizar_yaml(texto: str) -> CommentedMap:
    try:
        datos = crear_yaml().load(texto)
    except DuplicateKeyError as error:
        linea, columna = _posicion_de_marca(error)
        raise ErrorLecturaProtocolo(
            [
                ProblemaLectura(
                    f"clave duplicada en la línea {linea}, columna {columna}",
                    linea=linea,
                    columna=columna,
                )
            ]
        ) from None
    except YAMLError as error:
        linea, columna = _posicion_de_marca(error)
        detalle = getattr(error, "problem", None) or str(error)
        posicion = f" en la línea {linea}, columna {columna}" if linea is not None else ""
        raise ErrorLecturaProtocolo(
            [
                ProblemaLectura(
                    f"YAML mal formado{posicion} (detalle del analizador: {detalle})",
                    linea=linea,
                    columna=columna,
                )
            ]
        ) from None
    if datos is None:
        raise ErrorLecturaProtocolo([ProblemaLectura("el archivo está vacío")])
    if not isinstance(datos, CommentedMap):
        raise ErrorLecturaProtocolo(
            [ProblemaLectura("la raíz del protocolo debe ser un mapa de claves y valores")]
        )
    return datos


def _posicion_de_marca(error: YAMLError) -> tuple[int | None, int | None]:
    """Línea y columna (desde 1) donde el analizador detectó el problema."""
    marca = getattr(error, "problem_mark", None) or getattr(error, "context_mark", None)
    if marca is None:
        return None, None
    return marca.line + 1, marca.column + 1


def _verificar_version_esquema(datos: CommentedMap) -> None:
    if "version_esquema" not in datos:
        return  # el esquema lo reporta como campo obligatorio ausente
    version = datos["version_esquema"]
    if isinstance(version, bool) or version != VERSION_ESQUEMA:
        linea, columna = posicion_en_yaml(datos, ("version_esquema",))
        raise ErrorLecturaProtocolo(
            [
                ProblemaLectura(
                    f"versión de esquema no soportada: {version!r}; "
                    f"este agente admite la versión {VERSION_ESQUEMA}",
                    ubicacion="version_esquema",
                    linea=linea,
                    columna=columna,
                )
            ]
        )


def formatear_ubicacion(ruta: Sequence[str | int]) -> str:
    """Convierte una ruta de claves e índices en texto, p. ej. 'criterios.inclusion[0].fase'."""
    partes: list[str] = []
    for paso in ruta:
        if isinstance(paso, int):
            partes.append(f"[{paso}]")
        else:
            partes.append(f".{paso}" if partes else paso)
    return "".join(partes)


def posicion_en_yaml(
    datos: CommentedMap, ruta: Sequence[str | int]
) -> tuple[int | None, int | None]:
    """Línea y columna (desde 1) del nodo más profundo de `ruta` que existe en `datos`."""
    posicion: tuple[int | None, int | None] = (None, None)
    nodo: Any = datos
    for paso in ruta:
        if isinstance(nodo, CommentedMap) and paso in nodo:
            linea, columna = nodo.lc.key(paso)
        elif isinstance(nodo, CommentedSeq) and isinstance(paso, int) and 0 <= paso < len(nodo):
            linea, columna = nodo.lc.item(paso)
        else:
            break
        posicion = (linea + 1, columna + 1)
        nodo = nodo[paso]
    return posicion


def _problema_de_esquema(detalle: ErrorDetails, datos: CommentedMap) -> ProblemaLectura:
    ruta = [paso for paso in detalle["loc"] if isinstance(paso, str | int)]
    ubicacion = formatear_ubicacion(ruta) or None
    linea, columna = posicion_en_yaml(datos, ruta)
    return ProblemaLectura(
        mensaje=_mensaje_de_esquema(detalle),
        ubicacion=ubicacion,
        linea=linea,
        columna=columna,
    )


_MENSAJES_POR_TIPO = {
    "missing": "falta este campo obligatorio",
    "extra_forbidden": "clave no permitida por el esquema",
    "string_type": "se esperaba un texto",
    "int_type": "se esperaba un número entero",
    "float_type": "se esperaba un número",
    "bool_type": "se esperaba true o false",
    "list_type": "se esperaba una lista",
    "model_type": "se esperaba un mapa de claves y valores",
    "dict_type": "se esperaba un mapa de claves y valores",
}


def _mensaje_de_esquema(detalle: ErrorDetails) -> str:
    """Traduce al español el mensaje de un error de validación de pydantic."""
    tipo = detalle["type"]
    contexto = detalle.get("ctx") or {}
    if tipo == "literal_error":
        permitidos = str(contexto.get("expected", "")).replace(" or ", " o ")
        mensaje = f"valor no permitido; se admite {permitidos}"
    elif tipo == "string_pattern_mismatch":
        mensaje = f"no cumple el formato exigido ({contexto.get('pattern')})"
    elif tipo == "too_short":
        mensaje = f"debe tener al menos {contexto.get('min_length')} elementos"
    elif tipo in _MENSAJES_POR_TIPO:
        mensaje = _MENSAJES_POR_TIPO[tipo]
    else:
        mensaje = f"no cumple el esquema ({tipo}: {detalle['msg']})"
    if tipo not in ("missing", "extra_forbidden"):
        mensaje += f"; valor recibido: {_resumir(detalle['input'])}"
    return mensaje


def _resumir(valor: object, largo_maximo: int = 60) -> str:
    texto = repr(a_python(valor))
    return texto if len(texto) <= largo_maximo else texto[: largo_maximo - 1] + "…"


# --- Fusión del modelo sobre el YAML original ---------------------------------


def _fusionar_mapa(destino: CommentedMap, origen: Mapping[str, Any]) -> None:
    for clave in [clave for clave in destino if clave not in origen]:
        del destino[clave]
    for clave, valor in origen.items():
        if clave in destino:
            destino[clave] = _fusionar_valor(destino[clave], valor)
        else:
            destino[clave] = _a_ruamel(valor)


def _fusionar_valor(actual: Any, nuevo: Any) -> Any:
    """Devuelve el valor que debe quedar en el YAML; reutiliza `actual` si es posible."""
    if isinstance(actual, CommentedMap) and isinstance(nuevo, Mapping):
        _fusionar_mapa(actual, nuevo)
        return actual
    if isinstance(actual, CommentedSeq) and isinstance(nuevo, list):
        if _tiene_ids(actual) and _tiene_ids(nuevo):
            _fusionar_lista_por_id(actual, nuevo)
        else:
            _fusionar_lista_por_posicion(actual, nuevo)
        return actual
    if _iguales(actual, nuevo):
        return actual
    if isinstance(actual, ScalarString) and isinstance(nuevo, str):
        return type(actual)(nuevo)  # conserva el estilo de comillas
    return _a_ruamel(nuevo)


def _tiene_ids(lista: Sequence[Any]) -> bool:
    """Indica si todos los elementos son mapas con un `id` de texto único."""
    if not lista or not all(isinstance(e, Mapping) and isinstance(e.get("id"), str) for e in lista):
        return False
    ids = [elemento["id"] for elemento in lista]
    return len(set(ids)) == len(ids)


def _fusionar_lista_por_id(destino: CommentedSeq, origen: list[Any]) -> None:
    anteriores = {str(elemento["id"]): elemento for elemento in destino}
    resultado = []
    for elemento in origen:
        anterior = anteriores.get(elemento["id"])
        if anterior is None:
            resultado.append(_a_ruamel(elemento))
        else:
            _fusionar_mapa(anterior, elemento)
            resultado.append(anterior)
    if [id(e) for e in resultado] != [id(e) for e in destino]:
        destino[:] = resultado


def _fusionar_lista_por_posicion(destino: CommentedSeq, origen: list[Any]) -> None:
    del destino[len(origen) :]
    for posicion, valor in enumerate(origen):
        if posicion < len(destino):
            destino[posicion] = _fusionar_valor(destino[posicion], valor)
        else:
            destino.append(_a_ruamel(valor))
    # Una lista vacía leída como [] no guarda estilo; se escribe en línea si es de escalares.
    if destino.fa.flow_style() is None and _son_escalares(origen):
        destino.fa.set_flow_style()


def _iguales(actual: Any, nuevo: Any) -> bool:
    """Igualdad que no confunde `True` con `1`, pero sí iguala `1` y `1.0`."""
    anterior = a_python(actual)
    if isinstance(anterior, bool) or isinstance(nuevo, bool):
        return type(anterior) is type(nuevo) and anterior == nuevo
    if isinstance(anterior, int | float) and isinstance(nuevo, int | float):
        return anterior == nuevo
    return type(anterior) is type(nuevo) and bool(anterior == nuevo)


def _a_ruamel(valor: Any) -> Any:
    """Convierte un valor nuevo a tipos de ruamel: mapas en bloque, escalares en línea."""
    if isinstance(valor, Mapping):
        mapa = CommentedMap()
        for clave, dato in valor.items():
            mapa[clave] = _a_ruamel(dato)
        return mapa
    if isinstance(valor, list):
        lista = CommentedSeq(_a_ruamel(elemento) for elemento in valor)
        if _son_escalares(valor):
            lista.fa.set_flow_style()  # listas de escalares en línea: [A, B]
        return lista
    return valor


def _son_escalares(valores: list[Any]) -> bool:
    return all(not isinstance(valor, Mapping | list) for valor in valores)
