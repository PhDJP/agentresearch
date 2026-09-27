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
import re
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
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
    """Un protocolo leído: el YAML original con comentarios y su modelo validado.

    `comentarios_de_seccion` guarda, por cada clave de primer nivel del texto
    leído, las líneas de comentario que la precedían. La escritura las vuelve
    a poner antes de su clave (ver `texto_protocolo()`). Es `None` si el
    documento no se construyó desde un texto, y entonces no se restaura nada.
    """

    datos: CommentedMap
    protocolo: Protocolo
    comentarios_de_seccion: dict[str, tuple[str, ...]] | None = None


def texto_plantilla() -> str:
    """Devuelve el texto de la plantilla comentada del protocolo."""
    recurso = files("agentresearch.protocolo").joinpath("plantillas", "protocolo.yaml")
    return recurso.read_bytes().decode("utf-8")


def leer_protocolo(ruta: Path | str) -> DocumentoProtocolo:
    """Lee y valida contra el esquema un archivo de protocolo.

    Lanza `ErrorLecturaProtocolo` si el archivo no existe, no es UTF-8, no es
    YAML válido o no cumple el esquema.
    """
    return decodificar_protocolo(leer_bytes_protocolo(ruta))


def leer_bytes_protocolo(ruta: Path | str) -> bytes:
    """Lee los bytes del archivo del protocolo, una sola vez.

    Los comandos del ciclo de vida validan, calculan el diff y calculan el
    hash sobre estos mismos bytes (ADR-0008, punto 3).
    """
    ruta = Path(ruta)
    try:
        return ruta.read_bytes()
    except FileNotFoundError:
        raise ErrorLecturaProtocolo([ProblemaLectura(f"el archivo no existe: {ruta}")]) from None
    except OSError as error:
        raise ErrorLecturaProtocolo(
            [ProblemaLectura(f"no se pudo leer el archivo {ruta}: {error.strerror}")]
        ) from None


def decodificar_protocolo(contenido: bytes) -> DocumentoProtocolo:
    """Decodifica en UTF-8, analiza y valida contra el esquema los bytes de un protocolo."""
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
    return DocumentoProtocolo(
        datos=datos,
        protocolo=protocolo,
        comentarios_de_seccion=_comentarios_de_seccion(texto, set(datos)),
    )


def texto_protocolo(documento: DocumentoProtocolo) -> str:
    """Serializa el documento a texto YAML, con fin de línea LF.

    Restaura los comentarios de sección de primer nivel. ruamel.yaml guarda el
    comentario que precede a una clave como comentario posterior al último
    nodo de la sección anterior (ADR-0006, Consecuencias). Por eso, al vaciar
    esa sección el comentario se pierde, y al agregarle un elemento al final
    queda antes de ese elemento y no antes de su clave. Aquí cada clave de
    primer nivel recupera las líneas de comentario que la precedían al leer el
    archivo; en un estudio, el protocolo nace de la plantilla, así que son los
    comentarios de la plantilla con las notas que agregue el investigador. Un
    archivo que sigue la plantilla sale idéntico, y uno sin comentarios de
    sección sigue sin ellos.
    """
    salida = io.StringIO()
    crear_yaml().dump(documento.datos, salida)
    texto = salida.getvalue()
    if documento.comentarios_de_seccion is None:
        return texto
    return _restaurar_comentarios_de_seccion(texto, documento.comentarios_de_seccion)


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


def analizar_fragmento(contenido: bytes) -> CommentedMap:
    """Decodifica en UTF-8 y analiza un fragmento YAML, sin validarlo contra el esquema.

    Sirve para leer una sección que se va a escribir en el protocolo. Lanza
    `ErrorLecturaProtocolo` si no es UTF-8, no es YAML válido, tiene claves
    duplicadas o su raíz no es un mapa.
    """
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        raise ErrorLecturaProtocolo(
            [ProblemaLectura("el archivo no está codificado en UTF-8")]
        ) from None
    return _analizar_yaml(texto)


def reemplazar_seccion(
    documento: DocumentoProtocolo, seccion: str, valor: Any, protocolo: Protocolo
) -> None:
    """Reemplaza la sección de primer nivel `seccion` por `valor`, leído con ruamel.yaml.

    `protocolo` es el modelo ya validado con la sección nueva. La sección se
    fusiona como en `actualizar_documento()`: lo que no está en `valor` se
    elimina, lo que no cambia conserva sus comentarios y su estilo, y lo nuevo
    conserva las comillas con que se escribió en `valor`.
    """
    documento.datos[seccion] = _fusionar_valor(documento.datos[seccion], valor)
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
            [ProblemaLectura("la raíz del documento debe ser un mapa de claves y valores")]
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


def describir_error_de_esquema(detalle: ErrorDetails) -> str:
    """Describe en español un error de pydantic, con su ubicación: `opciones[0].pros: …`."""
    ruta = [paso for paso in detalle["loc"] if isinstance(paso, str | int)]
    ubicacion = formatear_ubicacion(ruta)
    mensaje = _mensaje_de_esquema(detalle)
    return f"{ubicacion}: {mensaje}" if ubicacion else mensaje


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


# --- Comentarios de sección de primer nivel -----------------------------------

_CLAVE_DE_PRIMER_NIVEL = re.compile(r"([A-Za-z_][A-Za-z0-9_]*):(?: |$)")


def _clave_de_primer_nivel(linea: str, claves: AbstractSet[str]) -> str | None:
    """La clave de primer nivel que abre `linea`, si es una de `claves`."""
    coincidencia = _CLAVE_DE_PRIMER_NIVEL.match(linea)
    if coincidencia is None or coincidencia.group(1) not in claves:
        return None
    return coincidencia.group(1)


def _comentarios_de_seccion(texto: str, claves: AbstractSet[str]) -> dict[str, tuple[str, ...]]:
    """Por cada clave de primer nivel, las líneas de comentario (columna 0) que la preceden."""
    lineas = texto.split("\n")
    comentarios: dict[str, tuple[str, ...]] = {}
    for indice, linea in enumerate(lineas):
        clave = _clave_de_primer_nivel(linea, claves)
        if clave is None:
            continue
        inicio = indice
        while inicio > 0 and lineas[inicio - 1].startswith("#"):
            inicio -= 1
        comentarios[clave] = tuple(lineas[inicio:indice])
    return comentarios


def _restaurar_comentarios_de_seccion(texto: str, esperados: Mapping[str, tuple[str, ...]]) -> str:
    """Quita las líneas de comentario de sección donde estén y las pone antes de su clave.

    Solo mueve líneas de columna 0 idénticas a un comentario de sección; los
    demás comentarios se quedan donde los dejó ruamel.yaml.
    """
    de_seccion = {linea for bloque in esperados.values() for linea in bloque}
    resultado: list[str] = []
    for linea in texto.split("\n"):
        if linea in de_seccion:
            continue
        clave = _clave_de_primer_nivel(linea, esperados.keys())
        if clave is not None:
            resultado.extend(esperados[clave])
        resultado.append(linea)
    return "\n".join(resultado)


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
    nuevo = a_python(nuevo)
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
