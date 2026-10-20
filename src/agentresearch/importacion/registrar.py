"""`importar registrar`: registra una búsqueda manual en el estudio (ADR-0010; especificación 2c).

Orden (especificación 2c):

1. valida todo sin escribir y reporta todos los problemas a la vez (I-E01 a I-E13);
2. exige una terminal interactiva (I-E12);
3. pide la fecha y la hora de la búsqueda y su desfase (I-E04);
4. determina la versión del protocolo vigente en esa fecha y la ecuación esperada;
5. muestra el resumen completo;
6. pide la frase `registrar imp-NNNN`;
7. escribe: copias de los originales, `importaciones/imp-NNNN/`, el evento
   (punto de confirmación) y el anclaje.

Los registros completos no salen por la terminal ni por `--json`: lo que se
muestra es un resumen sin valores de campo (ADR-0010, punto 26).
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from agentresearch.importacion.busqueda import ResultadoBusqueda, leer_busqueda
from agentresearch.importacion.busqueda_archivo import (
    ArchivoDeBusqueda,
    leer_archivo_de_busqueda,
    problemas_de_mapeo,
)
from agentresearch.importacion.ecuacion_esperada import (
    EcuacionEsperadaCalculada,
    ErrorEcuacionEsperada,
    calcular_ecuacion_esperada,
    clasificar_relacion,
    version_vigente_en,
)
from agentresearch.importacion.fecha_hora import (
    DesfaseDelSistema,
    EntradaInvalida,
    con_desfase,
    desfase_del_sistema,
    interpretar_desfase,
    interpretar_fecha,
    interpretar_hora,
    texto_desfase,
    texto_iso,
    texto_iso_utc,
)
from agentresearch.importacion.git_ignorados import ComprobadorDeIgnorados, comprobar_con_git
from agentresearch.importacion.mapeo import ErrorDeMapeo, Mapeo
from agentresearch.protocolo.aprobacion import (
    ErrorCicloDeVida,
    OperacionCancelada,
    Reloj,
    confirmar_frase,
    exigir_terminal,
    leer_y_validar,
    problemas_de_persona,
)
from agentresearch.protocolo.ciclo_de_vida import (
    EstadoRegistro,
    VersionRegistrada,
    escribir_anclaje,
    falta_anclaje,
)
from agentresearch.protocolo.entradas import ErrorEntrada
from agentresearch.protocolo.estudio import RutasProtocolo
from agentresearch.protocolo.eventos import PersonaHumana
from agentresearch.protocolo.eventos_busqueda import (
    CARPETA_IMPORTACIONES,
    CARPETA_ORIGINALES,
    TIPO_BUSQUEDA_REGISTRADA,
    ArchivoBusqueda,
    CampoSoloLocal,
    ConfiguracionRegistrada,
    DatosBusquedaRegistrada,
    EcuacionEjecutada,
    EcuacionEsperada,
    MotivoSoloLocal,
    PoliticaRegistrada,
)
from agentresearch.protocolo.terminal import Terminal
from agentresearch.registros import (
    CAMPOS_HABILITABLES,
    VERSION_NORMALIZACION,
    ConfiguracionPublicacion,
    ErrorConfiguracionPublicacion,
    LimiteDePosicionExcedido,
    PoliticaDatos,
    Registro,
    campos_versionables,
    cargar_configuracion,
    cargar_politica,
    construir_registros,
    hash_politica,
    registro_versionable,
    serializar_registros_jsonl,
    serializar_vista_csv,
)
from agentresearch.trazabilidad import (
    Anclaje,
    EventoRegistro,
    RegistroEncadenado,
    escribir_atomico,
    hash_bytes,
    hash_texto,
)

NOMBRE_CONFIGURACION = "publicacion_datos.yaml"
INTENTOS_DE_ENTRADA = 3
CAMPOS_DEL_REGISTRO_NUNCA_PUBLICABLES = (
    "resumen",
    "palabras_clave_autor",
    "palabras_clave_indexadas",
)
"""Campos del registro normalizado que la política declara `nunca_publicables`."""

_HASHES_DE_LA_CARPETA = ("hash_importacion_json", "hash_registros_jsonl", "hash_registros_csv")


class ErrorRegistro(ErrorCicloDeVida):
    """La búsqueda no se puede registrar; `errores` explica por qué, sin haber escrito nada."""

    def __init__(self, errores: list[str], advertencias: list[str] | None = None) -> None:
        super().__init__(errores)
        self.advertencias = advertencias or []


@dataclass(frozen=True, slots=True)
class ResultadoRegistro:
    """Una búsqueda ya registrada."""

    id_importacion: str
    carpeta: str
    evento: EventoRegistro
    anclaje: Anclaje
    anclaje_recreado: bool
    advertencias: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        datos = self.evento.datos
        return {
            "id_importacion": self.id_importacion,
            "carpeta": self.carpeta,
            "evento": self.evento.id,
            "tipo_evento": self.evento.tipo,
            "fuente": datos["fuente"],
            "fecha_hora_busqueda": datos["fecha_hora_busqueda"],
            "fecha_hora_busqueda_utc": datos["fecha_hora_busqueda_utc"],
            "version_protocolo": datos["version_protocolo"],
            "relacion_ecuacion": datos["relacion_ecuacion"],
            "resultados_interfaz": datos["resultados_interfaz"],
            "registros_leidos": datos["registros_leidos"],
            "archivos": [
                {k: a[k] for k in ("nombre_original", "formato", "hash", "registros", "copia")}
                for a in datos["archivos"]
            ],
            "campos_versionados": datos["campos_versionados"],
            "campos_solo_locales": datos["campos_solo_locales"],
            "anclaje": str(self.anclaje),
            "anclaje_recreado": self.anclaje_recreado,
            "advertencias": self.advertencias,
        }


@dataclass(frozen=True, slots=True)
class _Preparacion:
    """Todo lo validado antes de pedir nada al investigador."""

    rutas: RutasProtocolo
    estado: EstadoRegistro
    declarada: ArchivoDeBusqueda
    lectura: ResultadoBusqueda
    mapeo: Mapeo | None
    rutas_origen: list[Path]
    id_importacion: str
    politica: PoliticaDatos
    configuracion: ConfiguracionPublicacion
    hash_configuracion: str
    advertencias: list[str]


def registrar_busqueda(
    archivo_busqueda: Path | str,
    registrado_por: str,
    estudio: Path | str,
    terminal: Terminal,
    reloj: Reloj | None = None,
    desfase_sistema: DesfaseDelSistema | None = None,
    comprobador: ComprobadorDeIgnorados | None = None,
) -> ResultadoRegistro:
    """Registra una búsqueda manual. Lanza `ErrorRegistro` o `OperacionCancelada` sin escribir."""
    ahora = reloj or (lambda: datetime.now(UTC))
    desfase_de = desfase_sistema or desfase_del_sistema
    preparacion = _preparar(
        Path(archivo_busqueda),
        registrado_por,
        Path(estudio),
        comprobador or comprobar_con_git,
        ahora,
    )
    try:
        exigir_terminal(terminal)
    except ErrorCicloDeVida as error:
        raise ErrorRegistro([f"I-E12: {mensaje}" for mensaje in error.errores]) from None

    momento, aviso_horario = _pedir_fecha_hora(terminal, preparacion, ahora, desfase_de)
    version = version_vigente_en(preparacion.estado, momento)
    if version is None:  # pragma: no cover - I-E04 ya exigió una aprobación anterior
        raise ErrorRegistro(["I-E04: no hay una versión del protocolo vigente en esa fecha"])
    esperada, relacion = _ecuacion(preparacion, version)

    armado = _armar(preparacion, momento, version, esperada, relacion, registrado_por)
    terminal.mostrar(_resumen(preparacion, armado.datos, aviso_horario))
    confirmar_frase(terminal, f"registrar {preparacion.id_importacion}")

    evento, anclaje, recreado = _escribir(preparacion, armado, ahora)
    return ResultadoRegistro(
        id_importacion=preparacion.id_importacion,
        carpeta=armado.datos.carpeta,
        evento=evento,
        anclaje=anclaje,
        anclaje_recreado=recreado,
        advertencias=preparacion.advertencias,
    )


# --- 1. Validación sin escribir ---------------------------------------------------


def _preparar(
    archivo_busqueda: Path,
    registrado_por: str,
    estudio: Path,
    comprobador: ComprobadorDeIgnorados,
    ahora: Reloj,
) -> _Preparacion:
    errores: list[str] = []
    advertencias: list[str] = []
    rutas = RutasProtocolo.desde(estudio / "protocolo" / "protocolo.yaml")

    try:
        declarada = leer_archivo_de_busqueda(archivo_busqueda)
    except ErrorEntrada as error:
        raise ErrorRegistro(error.errores) from None
    errores += problemas_de_mapeo(declarada)

    lectura_protocolo, estado, validacion = leer_y_validar(rutas)
    bloqueantes = [h for h in validacion.errores if h.id_regla in ("P-E00", "P-E09", "P-E10")]
    if bloqueantes or estado.ultima_version is None:
        errores += [f"I-E01: {h}" for h in bloqueantes]
        if estado.ultima_version is None and not bloqueantes:
            errores.append(
                "I-E01: el protocolo no está vigente según el registro; apruébelo con "
                "`agentresearch protocolo aprobar`"
            )
    protocolo = lectura_protocolo.documento.protocolo if lectura_protocolo.documento else None
    if protocolo is not None:
        declaradas = {f.id.strip().lower() for f in protocolo.fuentes if f.tipo == "exportacion"}
        if declarada.fuente.strip().lower() not in declaradas:
            errores.append(
                f"I-E02: la fuente «{declarada.fuente}» no está declarada en `fuentes` del "
                "protocolo con `tipo: exportacion`"
            )
        errores += [
            f"I-E11: {mensaje}"
            for mensaje in problemas_de_persona(protocolo, registrado_por, "--registrado-por")
        ]

    politica = cargar_politica()
    configuracion, hash_configuracion = _cargar_configuracion(
        rutas.estudio, politica, errores, ahora
    )

    mapeo, rutas_origen, lectura = _leer_archivos(declarada, errores)
    errores += _problemas_de_archivos(lectura, estado)

    id_importacion = f"imp-{len(estado.busquedas) + 1:04d}"
    errores += _problemas_de_git(rutas.estudio, id_importacion, rutas_origen, comprobador)

    if errores:
        raise ErrorRegistro(errores, advertencias)
    assert configuracion is not None and hash_configuracion is not None
    return _Preparacion(
        rutas=rutas,
        estado=estado,
        declarada=declarada,
        lectura=lectura,
        mapeo=mapeo,
        rutas_origen=rutas_origen,
        id_importacion=id_importacion,
        politica=politica,
        configuracion=configuracion,
        hash_configuracion=hash_configuracion,
        advertencias=advertencias,
    )


def _cargar_configuracion(
    estudio: Path, politica: PoliticaDatos, errores: list[str], ahora: Reloj
) -> tuple[ConfiguracionPublicacion | None, str | None]:
    ruta = estudio / NOMBRE_CONFIGURACION
    try:
        contenido = ruta.read_bytes()
    except OSError:
        contenido = None
    try:
        configuracion = cargar_configuracion(ruta, politica, ahora)
    except ErrorConfiguracionPublicacion as error:
        errores += [f"I-E13: {NOMBRE_CONFIGURACION}: {problema}" for problema in error.problemas]
        return None, None
    assert contenido is not None
    return configuracion, hash_bytes(contenido)


def _leer_archivos(
    declarada: ArchivoDeBusqueda, errores: list[str]
) -> tuple[Mapeo | None, list[Path], ResultadoBusqueda]:
    rutas_origen = [Path(texto) for texto in declarada.archivos]
    mapeo: Mapeo | None = None
    if declarada.mapeo is not None and declarada.formato == "csv":
        try:
            mapeo = Mapeo.cargar(Path(declarada.mapeo))
        except ErrorDeMapeo as error:
            errores.append(f"I-E07: no se pudo leer el archivo de mapeo: {error}")
    sin_leer = ResultadoBusqueda(formato=declarada.formato, fuente=declarada.fuente)
    if declarada.formato == "csv" and mapeo is None:
        return mapeo, rutas_origen, sin_leer
    try:
        lectura = leer_busqueda(rutas_origen, declarada.formato, declarada.fuente, mapeo)
    except ValueError as error:
        errores.append(f"I-E07: {error}")
        return mapeo, rutas_origen, sin_leer
    return mapeo, rutas_origen, lectura


def _problemas_de_archivos(lectura: ResultadoBusqueda, estado: EstadoRegistro) -> list[str]:
    problemas: list[str] = []
    for no_leido in lectura.no_leidos:
        problemas.append(f"I-E07: no se pudo abrir {no_leido.archivo}: {no_leido.motivo}")
    for archivo in lectura.archivos:
        for hallazgo in archivo.errores:
            regla = "I-E06" if hallazgo.regla == "L-E03" else "I-E07"
            donde = f"línea {hallazgo.linea}" if hallazgo.linea is not None else "archivo"
            problemas.append(
                f"{regla}: {archivo.archivo}, {donde} [{hallazgo.regla}]: {hallazgo.mensaje}"
            )
    for hallazgo in lectura.hallazgos_entre_archivos:
        if hallazgo.severidad == "error":
            donde = f"línea {hallazgo.linea}" if hallazgo.linea is not None else "archivo"
            problemas.append(
                f"I-E06: {hallazgo.archivo}, {donde} [{hallazgo.regla}]: {hallazgo.mensaje}"
            )
    registrados = {
        archivo.hash: busqueda.datos.id_importacion
        for busqueda in estado.busquedas
        for archivo in busqueda.datos.archivos
    }
    vistos: dict[str, str] = {}
    nombres: dict[str, str] = {}
    for archivo in lectura.archivos:
        if archivo.hash_archivo in registrados:
            problemas.append(
                f"I-E05: {archivo.archivo} ya está registrado en la importación "
                f"{registrados[archivo.hash_archivo]}"
            )
        elif archivo.hash_archivo in vistos:
            problemas.append(
                f"I-E05: {archivo.archivo} es idéntico a {vistos[archivo.hash_archivo]}, que "
                "aparece antes en la misma búsqueda"
            )
        vistos.setdefault(archivo.hash_archivo, archivo.archivo)
        if archivo.archivo in nombres and archivo.hash_archivo != nombres[archivo.archivo]:
            problemas.append(
                f"I-E05: dos archivos de la búsqueda se llaman {archivo.archivo}; renombre uno, "
                "porque las copias van juntas en una carpeta"
            )
        nombres.setdefault(archivo.archivo, archivo.hash_archivo)
    return problemas


def _problemas_de_git(
    raiz: Path,
    id_importacion: str,
    rutas_origen: Sequence[Path],
    comprobador: ComprobadorDeIgnorados,
) -> list[str]:
    destinos = [
        raiz / CARPETA_ORIGINALES / id_importacion / ruta.name
        for ruta in dict.fromkeys(rutas_origen)
    ]
    dentro = []
    for ruta in rutas_origen:
        try:
            absoluta = ruta.resolve()
            absoluta.relative_to(raiz)
        except (OSError, ValueError):
            continue
        dentro.append(absoluta)
    return [f"I-E10: {mensaje}" for mensaje in comprobador(raiz, [*destinos, *dentro])]


# --- 3. Fecha y hora ---------------------------------------------------------------


def _pedir_fecha_hora(
    terminal: Terminal, preparacion: _Preparacion, ahora: Reloj, desfase_de: DesfaseDelSistema
) -> tuple[datetime, str | None]:
    fecha = _preguntar(terminal, "Fecha de la búsqueda (AAAA-MM-DD): ", interpretar_fecha)
    hora = _preguntar(
        terminal, "Hora de la búsqueda, tal como la vio en su reloj (HH:MM): ", interpretar_hora
    )
    sin_zona = datetime.combine(fecha, hora)
    propuesto = desfase_de(sin_zona)
    texto = terminal.preguntar(
        f"Desfase respecto de UTC en esa fecha [{texto_desfase(propuesto)}]; pulse Enter para "
        "aceptarlo o escriba otro (±HH:MM): "
    )
    if texto is None:
        raise OperacionCancelada("no se confirmó el desfase")
    desfase = interpretar_desfase(texto) if texto.strip() else propuesto
    momento = con_desfase(fecha, hora, desfase)

    actual = desfase_de(ahora())
    aviso = None
    if desfase != actual:
        aviso = (
            f"aviso: el desfase de esa fecha ({texto_desfase(desfase)}) difiere del actual "
            f"({texto_desfase(actual)}); la fecha cae en otro periodo de horario de verano"
        )
        terminal.mostrar(aviso)

    if momento.astimezone(UTC) > ahora().astimezone(UTC):
        raise ErrorRegistro(["I-E04: la fecha de la búsqueda es futura"])
    primera = preparacion.estado.versiones[0]
    aprobacion = datetime.fromisoformat(primera.evento.fecha_hora_utc)
    if momento.astimezone(UTC) < aprobacion.astimezone(UTC):
        raise ErrorRegistro(
            [
                "I-E04: la fecha de la búsqueda es anterior a la aprobación del protocolo "
                f"({primera.evento.fecha_hora_utc})"
            ]
        )
    return momento, aviso


def _preguntar[T](terminal: Terminal, pregunta: str, interpretar: Callable[[str], T]) -> T:
    for _intento in range(INTENTOS_DE_ENTRADA):
        respuesta = terminal.preguntar(pregunta)
        if respuesta is None:
            raise OperacionCancelada("la entrada terminó antes de recibir la respuesta")
        try:
            return interpretar(respuesta)
        except EntradaInvalida as error:
            terminal.mostrar(f"  {error}")
    raise OperacionCancelada("demasiados intentos con una respuesta no válida")


# --- 4. Ecuación -------------------------------------------------------------------


def _ecuacion(
    preparacion: _Preparacion, version: VersionRegistrada
) -> tuple[EcuacionEsperadaCalculada, str]:
    declarada = preparacion.declarada
    try:
        esperada = calcular_ecuacion_esperada(preparacion.estado, version, declarada.fuente)
    except ErrorEcuacionEsperada as error:
        raise ErrorRegistro([f"I-E01: {error}"]) from None
    relacion = clasificar_relacion(declarada.fuente, esperada.texto, declarada.ecuacion_ejecutada)
    errores: list[str] = []
    if relacion == "desviacion" and not declarada.justificacion_ecuacion.strip():
        errores.append(
            "I-E09: la ecuación ejecutada difiere de la del protocolo y no hay "
            "`justificacion_ecuacion`"
        )
    leidos = preparacion.lectura.numero_registros
    if leidos != declarada.resultados_interfaz and not declarada.justificacion_diferencia.strip():
        errores.append(
            f"I-E08: la interfaz mostró {declarada.resultados_interfaz} resultados y se leyeron "
            f"{leidos} registros, y no hay `justificacion_diferencia`"
        )
    if errores:
        raise ErrorRegistro(errores)
    return esperada, relacion


# --- 5. Datos, campos y archivos ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Armado:
    """Los datos del evento y los bytes de los archivos de la importación."""

    datos: DatosBusquedaRegistrada
    importacion_json: bytes
    jsonl: bytes
    csv: bytes


def _armar(
    preparacion: _Preparacion,
    momento: datetime,
    version: VersionRegistrada,
    esperada: EcuacionEsperadaCalculada,
    relacion: str,
    registrado_por: str,
) -> _Armado:
    declarada = preparacion.declarada
    id_importacion = preparacion.id_importacion
    normalizados = [r for archivo in preparacion.lectura.archivos for r in archivo.registros]
    try:
        registros = construir_registros(id_importacion, normalizados)
    except LimiteDePosicionExcedido as error:
        raise ErrorRegistro([f"I-E07: {error}"]) from None

    campos = campos_versionables(declarada.fuente, preparacion.politica, preparacion.configuracion)
    versionados, solo_locales = _clasificar_campos(
        declarada.fuente, campos, registros, preparacion.configuracion
    )
    jsonl = serializar_registros_jsonl(registros, versionados)
    csv = serializar_vista_csv(jsonl)

    locales = [c.campo for c in solo_locales if c.motivo != "nunca_publicable"]
    if locales:
        preparacion.advertencias.append(
            "I-A01: estos campos se importan y se conservan en local, pero no se versionan (el "
            f"estudio no los habilita o su base está incompleta): {', '.join(locales)}"
        )

    archivos = [
        ArchivoBusqueda(
            nombre_original=archivo.archivo,
            formato=archivo.formato,
            hash=archivo.hash_archivo,
            registros=archivo.numero_registros,
            copia=f"{CARPETA_ORIGINALES}/{id_importacion}/{archivo.archivo}",
        ).model_dump(mode="json")
        for archivo in preparacion.lectura.archivos
    ]
    base: dict[str, Any] = {
        "id_importacion": id_importacion,
        "fuente": declarada.fuente,
        "plataforma": declarada.plataforma,
        "institucion_acceso": declarada.institucion_acceso,
        "cobertura": declarada.cobertura,
        "lematizacion": declarada.lematizacion,
        "filtros": declarada.filtros,
        "fecha_hora_busqueda": texto_iso(momento),
        "fecha_hora_busqueda_utc": texto_iso_utc(momento),
        "version_protocolo": version.version,
        "evento_version": version.evento.id,
        "ecuacion_esperada": EcuacionEsperada(
            texto=esperada.texto,
            hash=esperada.hash,
            origen=esperada.origen,
            version_agente=esperada.version_agente,
        ).model_dump(mode="json"),
        "ecuacion_ejecutada": EcuacionEjecutada(
            texto=declarada.ecuacion_ejecutada, hash=hash_texto(declarada.ecuacion_ejecutada)
        ).model_dump(mode="json"),
        "relacion_ecuacion": relacion,
        "justificacion_ecuacion": declarada.justificacion_ecuacion.strip(),
        "resultados_interfaz": declarada.resultados_interfaz,
        "registros_leidos": len(registros),
        "justificacion_diferencia": declarada.justificacion_diferencia.strip(),
        "archivos": archivos,
        "mapeo": preparacion.mapeo.hash if preparacion.mapeo is not None else None,
        "carpeta": f"{CARPETA_IMPORTACIONES}/{id_importacion}",
        "politica": PoliticaRegistrada(
            version=preparacion.politica.version, hash=hash_politica()
        ).model_dump(mode="json"),
        "configuracion_publicacion": ConfiguracionRegistrada(
            hash=preparacion.hash_configuracion
        ).model_dump(mode="json"),
        "version_normalizacion": VERSION_NORMALIZACION,
        "campos_versionados": versionados,
        "campos_solo_locales": [c.model_dump(mode="json") for c in solo_locales],
        "registrado_por": PersonaHumana(tipo="humano", id=registrado_por).model_dump(mode="json"),
    }
    importacion_json = (
        json.dumps(base, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    hashes = dict(
        zip(
            _HASHES_DE_LA_CARPETA,
            (hash_bytes(importacion_json), hash_bytes(jsonl), hash_bytes(csv)),
            strict=True,
        )
    )
    try:
        datos = DatosBusquedaRegistrada.model_validate({**base, **hashes})
    except ValueError as error:
        raise ErrorRegistro([f"los datos de la búsqueda no son coherentes: {error}"]) from None
    return _Armado(datos, importacion_json, jsonl, csv)


def _clasificar_campos(
    fuente: str,
    campos: Sequence[str],
    registros: Sequence[Registro],
    configuracion: ConfiguracionPublicacion,
) -> tuple[list[str], list[CampoSoloLocal]]:
    """Separa los campos que se versionan de los que quedan solo en local, con su motivo."""
    versionados = list(campos)
    if "id_fuente" in versionados and any(
        "id_fuente" not in registro_versionable(registro, campos) for registro in registros
    ):
        versionados.remove("id_fuente")  # rige por `doi` o `pmid`, que el estudio no habilitó
    entrada = configuracion.fuentes.get(fuente)
    solo_locales: list[CampoSoloLocal] = []
    for campo in CAMPOS_HABILITABLES:
        if campo in versionados:
            continue
        configurado = entrada.campos.get(campo) if entrada is not None else None
        motivo: MotivoSoloLocal = (
            "base_incompleta"
            if configurado is not None and not configurado.base.es_completa
            else "sin_habilitar"
        )
        solo_locales.append(CampoSoloLocal(campo=campo, motivo=motivo))
    solo_locales += [
        CampoSoloLocal(campo=campo, motivo="nunca_publicable")
        for campo in CAMPOS_DEL_REGISTRO_NUNCA_PUBLICABLES
    ]
    return versionados, solo_locales


# --- 6. Resumen --------------------------------------------------------------------


def _resumen(preparacion: _Preparacion, datos: DatosBusquedaRegistrada, aviso: str | None) -> str:
    esperada, ejecutada = datos.ecuacion_esperada, datos.ecuacion_ejecutada
    lineas = [
        f"Registro de la búsqueda {datos.id_importacion}",
        f"  fuente: {datos.fuente}",
        f"  plataforma: {datos.plataforma}",
        f"  institución de acceso: {datos.institucion_acceso}",
        f"  cobertura: {datos.cobertura}",
        f"  filtros: {'; '.join(datos.filtros) if datos.filtros else 'ninguno'}",
        f"  lematización: {datos.lematizacion if datos.lematizacion else 'no se informó'}",
        f"  fecha y hora local: {datos.fecha_hora_busqueda}",
        f"  fecha y hora UTC: {datos.fecha_hora_busqueda_utc}",
        f"  versión del protocolo vigente: {datos.version_protocolo} ({datos.evento_version})",
        f"  ecuación esperada ({esperada.origen}, agente {esperada.version_agente}):",
        f"    {esperada.texto}",
        "  ecuación ejecutada:",
        f"    {ejecutada.texto}",
        f"  relación: {datos.relacion_ecuacion}",
    ]
    if datos.relacion_ecuacion != "identica":
        lineas.append(f"  diferencia: {_diferencia(esperada.texto, ejecutada.texto)}")
    if datos.justificacion_ecuacion:
        lineas.append(f"  justificación de la ecuación: {datos.justificacion_ecuacion}")
    lineas.append("  archivos:")
    for archivo in datos.archivos:
        lineas.append(
            f"    - {archivo.nombre_original} ({archivo.formato}): {archivo.registros} registros, "
            f"{archivo.hash}"
        )
    lineas.append(
        f"  registros leídos: {datos.registros_leidos}; resultados de la interfaz: "
        f"{datos.resultados_interfaz}"
    )
    if datos.justificacion_diferencia:
        lineas.append(f"  justificación de la diferencia: {datos.justificacion_diferencia}")
    versionados = ", ".join(datos.campos_versionados) or "ninguno"
    lineas.append(f"  campos que se versionarán: {versionados}")
    if datos.campos_solo_locales:
        lineas.append("  campos que quedarán solo en local:")
        lineas += [
            f"    - {c.campo} ({_texto_motivo(c.motivo)})" for c in datos.campos_solo_locales
        ]
    for advertencia in preparacion.advertencias:
        lineas.append(f"  {advertencia}")
    if aviso:
        lineas.append(f"  {aviso}")
    return "\n".join(lineas)


def _texto_motivo(motivo: MotivoSoloLocal) -> str:
    return {
        "sin_habilitar": "el estudio no lo habilita",
        "base_incompleta": "su base está incompleta",
        "nunca_publicable": "nunca se publica",
    }[motivo]


def _diferencia(esperada: str, ejecutada: str) -> str:
    """Palabras que cambian: `-` solo en la esperada, `+` solo en la ejecutada."""
    a, b = esperada.split(), ejecutada.split()
    cambios: list[str] = []
    for etiqueta, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if etiqueta == "equal":
            continue
        if i2 > i1:
            cambios.append("- " + " ".join(a[i1:i2]))
        if j2 > j1:
            cambios.append("+ " + " ".join(b[j1:j2]))
    return "; ".join(cambios) if cambios else "solo cambian los espacios"


# --- 7. Escritura -------------------------------------------------------------------


def _escribir(
    preparacion: _Preparacion, armado: _Armado, ahora: Reloj
) -> tuple[EventoRegistro, Anclaje, bool]:
    """Copias, carpeta de la importación, evento y anclaje, en ese orden (ADR-0010, punto 18)."""
    rutas = preparacion.rutas
    datos = armado.datos
    raiz = rutas.estudio
    for ruta, archivo in zip(preparacion.rutas_origen, preparacion.lectura.archivos, strict=True):
        contenido = ruta.read_bytes()
        if hash_bytes(contenido) != archivo.hash_archivo:
            raise OperacionCancelada(
                f"{ruta.name} cambió mientras se confirmaba; vuelva a ejecutar el comando"
            )
        escribir_atomico(raiz.joinpath(*datos_copia(datos, archivo.archivo)), contenido)
    carpeta = raiz.joinpath(*datos.carpeta.split("/"))
    escribir_atomico(carpeta / "importacion.json", armado.importacion_json)
    escribir_atomico(carpeta / "registros.jsonl", armado.jsonl)
    escribir_atomico(carpeta / "registros.csv", armado.csv)

    registro = RegistroEncadenado(rutas.eventos, reloj=ahora)
    if registro.anclaje() != preparacion.estado.anclaje_actual:
        raise OperacionCancelada(
            "el registro de eventos cambió mientras se confirmaba; vuelva a ejecutar el comando"
        )
    recreado = falta_anclaje(rutas)
    evento = registro.agregar(TIPO_BUSQUEDA_REGISTRADA, datos.model_dump(mode="json"))
    anclaje = escribir_anclaje(rutas)
    return evento, anclaje, recreado


def datos_copia(datos: DatosBusquedaRegistrada, nombre: str) -> list[str]:
    """Partes de la ruta relativa de la copia del original `nombre`."""
    archivo = next(a for a in datos.archivos if a.nombre_original == nombre)
    return archivo.copia.split("/")
