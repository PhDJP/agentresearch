"""Pruebas del estado del registro y de las reglas de directorio P-E09 y P-E10 (ADR-0008).

Aquí los eventos de aprobación y de decisión se escriben a mano, imitando a los
comandos, para probar la lectura del registro con independencia de ellos.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from agentresearch.protocolo import (
    RutasProtocolo,
    actualizar_documento,
    decodificar_protocolo,
    leer_estado_registro,
    siguiente_version,
    texto_protocolo,
    validar_archivo,
)
from agentresearch.protocolo.ciclo_de_vida import escribir_anclaje, texto_anclaje
from agentresearch.trazabilidad import (
    Anclaje,
    RegistroEncadenado,
    escribir_atomico,
    hash_bytes,
)

HASH_FICTICIO = "sha256:" + "a" * 64


def _ids(ruta: Path) -> list[str]:
    return [hallazgo.id_regla for hallazgo in validar_archivo(ruta).hallazgos]


def _mensajes(ruta: Path, id_regla: str) -> list[str]:
    return [h.mensaje for h in validar_archivo(ruta).hallazgos if h.id_regla == id_regla]


def _texto_con(ruta: Path, estado: str, version: str) -> bytes:
    documento = decodificar_protocolo(ruta.read_bytes())
    nuevo = documento.protocolo.model_copy(deep=True)
    nuevo.estado = estado  # type: ignore[assignment]
    nuevo.metadatos.version_protocolo = version
    actualizar_documento(documento, nuevo)
    return texto_protocolo(documento).encode("utf-8")


def _aprobar_a_mano(ruta: Path, escribir_protocolo: bool = True) -> dict[str, Any]:
    """Imita `protocolo aprobar`: copia, evento, anclaje y protocolo, en ese orden."""
    rutas = RutasProtocolo.desde(ruta)
    revisado = ruta.read_bytes()
    nuevo = _texto_con(ruta, "vigente", "1.0.0")
    escribir_atomico(rutas.copia_de_version("1.0.0"), nuevo)
    datos: dict[str, Any] = {
        "version_anterior": "0.1.0",
        "version_protocolo": "1.0.0",
        "hash_revisado": hash_bytes(revisado),
        "hash_protocolo": hash_bytes(nuevo),
        "ruta_protocolo": "protocolo/protocolo.yaml",
        "ruta_version": "protocolo/versiones/1.0.0.yaml",
        "aprobado_por": {"tipo": "humano", "id": "investigador-1"},
        "advertencias": [],
    }
    RegistroEncadenado(rutas.eventos).agregar("protocolo_aprobado", datos)
    escribir_anclaje(rutas)
    if escribir_protocolo:
        escribir_atomico(ruta, nuevo)
    return datos


def _agregar_evento(ruta: Path, tipo: str, datos: dict[str, Any]) -> None:
    rutas = RutasProtocolo.desde(ruta)
    RegistroEncadenado(rutas.eventos).agregar(tipo, datos)
    escribir_anclaje(rutas)


def _decision(id_decision: str, reemplaza: str | None = None) -> dict[str, Any]:
    opcion = {"descripcion": "d", "pros": ["p"], "contras": ["c"], "referencias": ["r"]}
    return {
        "decision": {
            "id_decision": id_decision,
            "tema": "t",
            "pregunta": "p",
            "opciones": [{"id": "A", **opcion}, {"id": "B", **opcion}],
            "elegida": "A",
            "justificacion": "j",
            "propuesto_por": {"tipo": "llm", "modelo": "claude-opus-5-5"},
            "decidido_por": {"tipo": "humano", "id": "investigador-1"},
            "reemplaza": reemplaza,
        },
        "version_protocolo": "0.1.0",
        "estado_protocolo": "borrador",
        "hash_protocolo": HASH_FICTICIO,
    }


def _reemplazar_en(ruta: Path, viejo: str, nuevo: str) -> None:
    texto = ruta.read_text(encoding="utf-8")
    assert viejo in texto
    ruta.write_text(texto.replace(viejo, nuevo), encoding="utf-8", newline="\n")


# --- Borrador sin registro ---------------------------------------------------------


def test_un_borrador_sin_registro_no_tiene_hallazgos_de_directorio(
    protocolo_de_estudio: Path,
) -> None:
    resultado = validar_archivo(protocolo_de_estudio)

    assert resultado.hallazgos == []
    assert resultado.registro is not None
    assert resultado.registro["ruta"] == "protocolo/eventos.jsonl"
    assert resultado.registro["existe"] is False
    assert resultado.registro["numero_eventos"] is None
    assert resultado.registro["anclaje"] is None


# --- P-E10 -----------------------------------------------------------------------


@pytest.mark.parametrize("presente", ["anclaje.json", "versiones"])
def test_p_e10_si_falta_el_registro_pero_existe_el_anclaje_o_las_versiones(
    protocolo_de_estudio: Path, presente: str
) -> None:
    ruta = protocolo_de_estudio.parent / presente
    if presente == "versiones":
        ruta.mkdir()
    else:
        ruta.write_text("{}", encoding="utf-8")

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert mensaje.startswith(f"falta protocolo/eventos.jsonl, pero existe protocolo/{presente}")
    assert "copia huérfana" in mensaje


def test_p_e10_con_una_cadena_rota_indica_la_linea(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    _reemplazar_en(protocolo_de_estudio.parent / "eventos.jsonl", "investigador-1", "otra")

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert mensaje.startswith("la cadena de protocolo/eventos.jsonl está rota en la línea 1")
    assert "P-E09" not in _ids(protocolo_de_estudio)


def test_p_e10_detecta_eventos_finales_eliminados_con_el_anclaje(
    protocolo_de_estudio: Path,
) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    _agregar_evento(protocolo_de_estudio, "decision_propuesta", _decision("O1"))
    eventos = protocolo_de_estudio.parent / "eventos.jsonl"
    primera = eventos.read_text(encoding="utf-8").splitlines()[0]
    eventos.write_text(primera + "\n", encoding="utf-8", newline="\n")

    assert RegistroEncadenado(eventos).verificar().valido  # la cadena sola no lo detecta
    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert "no cumple protocolo/anclaje.json" in mensaje
    assert "se eliminaron eventos del final" in mensaje


def test_un_anclaje_atrasado_es_valido(protocolo_de_estudio: Path) -> None:
    """Si un fallo impide actualizar el anclaje, el registro lo sigue cumpliendo como prefijo."""
    _aprobar_a_mano(protocolo_de_estudio)
    rutas = RutasProtocolo.desde(protocolo_de_estudio)
    RegistroEncadenado(rutas.eventos).agregar("decision_propuesta", _decision("O1"))

    estado = leer_estado_registro(rutas)

    assert estado.integro
    assert estado.anclaje_guardado is not None
    assert estado.anclaje_guardado.numero_eventos == 1
    assert estado.anclaje_actual is not None
    assert estado.anclaje_actual.numero_eventos == 2


def test_sin_anclaje_guardado_el_registro_no_es_un_error(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    (protocolo_de_estudio.parent / "anclaje.json").unlink()

    assert _ids(protocolo_de_estudio) == []


@pytest.mark.parametrize(
    ("contenido", "fragmento"),
    [
        (b"{", "no es JSON válido"),
        (b'{"registro": "protocolo/eventos.jsonl"}', "falta este campo obligatorio"),
        (
            b'{"registro": "protocolo/eventos.jsonl", "numero_eventos": 1, '
            b'"hash_ultimo": "sha256:genesis"}',
            "hash no válido",
        ),
        (
            b'{"registro": "otro/eventos.jsonl", "numero_eventos": 0, '
            b'"hash_ultimo": "sha256:genesis"}',
            "ancla 'otro/eventos.jsonl'",
        ),
        (
            b'{"registro": "../fuera.jsonl", "numero_eventos": 0, "hash_ultimo": "sha256:genesis"}',
            "ruta relativa",
        ),
    ],
)
def test_p_e10_con_un_anclaje_no_valido(
    protocolo_de_estudio: Path, contenido: bytes, fragmento: str
) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    (protocolo_de_estudio.parent / "anclaje.json").write_bytes(contenido)

    mensajes = _mensajes(protocolo_de_estudio, "P-E10")

    assert mensajes
    assert any(fragmento in mensaje for mensaje in mensajes), mensajes


def test_p_e10_con_un_evento_que_no_cumple_su_esquema(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    _agregar_evento(protocolo_de_estudio, "protocolo_enmendado", {"version_anterior": "1.0.0"})

    mensajes = _mensajes(protocolo_de_estudio, "P-E10")

    assert mensajes
    assert all("evt-000002 (protocolo_enmendado)" in mensaje for mensaje in mensajes)


def test_p_e10_con_una_segunda_aprobacion(protocolo_de_estudio: Path) -> None:
    datos = _aprobar_a_mano(protocolo_de_estudio)
    _agregar_evento(protocolo_de_estudio, "protocolo_aprobado", datos)

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert "evt-000002 registra una segunda aprobación" in mensaje


def test_p_e10_con_una_aprobacion_de_otra_version(protocolo_de_estudio: Path) -> None:
    _agregar_evento(
        protocolo_de_estudio,
        "protocolo_aprobado",
        {
            "version_anterior": "0.1.0",
            "version_protocolo": "2.0.0",
            "hash_revisado": HASH_FICTICIO,
            "hash_protocolo": HASH_FICTICIO,
            "ruta_protocolo": "protocolo/protocolo.yaml",
            "ruta_version": "protocolo/versiones/2.0.0.yaml",
            "aprobado_por": {"tipo": "humano", "id": "investigador-1"},
            "advertencias": [],
        },
    )

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert "la aprobación fija la versión 1.0.0" in mensaje


def _datos_enmienda(**cambios: Any) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "version_anterior": "1.0.0",
        "version_protocolo": "1.1.0",
        "nivel": "menor",
        "hash_protocolo_anterior": HASH_FICTICIO,
        "hash_revisado": HASH_FICTICIO,
        "hash_protocolo": HASH_FICTICIO,
        "ruta_protocolo": "protocolo/protocolo.yaml",
        "ruta_version": "protocolo/versiones/1.1.0.yaml",
        "justificacion": "j",
        "efecto_esperado": "e",
        "enmendado_por": {"tipo": "humano", "id": "investigador-1"},
        "cambios": [],
        "solo_formato": True,
        "advertencias": [],
    }
    datos.update(cambios)
    return datos


def test_p_e10_con_una_enmienda_sin_aprobacion(protocolo_de_estudio: Path) -> None:
    _agregar_evento(protocolo_de_estudio, "protocolo_enmendado", _datos_enmienda())

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert "enmienda sin aprobación previa" in mensaje


def test_p_e10_con_una_version_que_no_sigue_el_nivel(protocolo_de_estudio: Path) -> None:
    aprobacion = _aprobar_a_mano(protocolo_de_estudio)
    _agregar_evento(
        protocolo_de_estudio,
        "protocolo_enmendado",
        _datos_enmienda(
            version_protocolo="2.0.0", hash_protocolo_anterior=aprobacion["hash_protocolo"]
        ),
    )

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert "el nivel menor lleva a 1.1.0" in mensaje


def test_p_e10_con_un_hash_anterior_que_no_encadena(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    _agregar_evento(protocolo_de_estudio, "protocolo_enmendado", _datos_enmienda())

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert "hash_protocolo_anterior no coincide" in mensaje


def test_p_e10_con_la_copia_de_una_version_alterada_o_ausente(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    copia = protocolo_de_estudio.parent / "versiones" / "1.0.0.yaml"
    copia.write_bytes(copia.read_bytes() + b"# alterada\n")

    [alterada] = _mensajes(protocolo_de_estudio, "P-E10")
    copia.unlink()
    [ausente] = _mensajes(protocolo_de_estudio, "P-E10")

    assert alterada.startswith("la copia protocolo/versiones/1.0.0.yaml no coincide con el hash")
    assert ausente.startswith("falta la copia protocolo/versiones/1.0.0.yaml")


def test_p_e10_con_la_copia_guardada_en_otra_ruta(protocolo_de_estudio: Path) -> None:
    datos = _aprobar_a_mano(protocolo_de_estudio, escribir_protocolo=False)
    eventos = protocolo_de_estudio.parent / "eventos.jsonl"
    eventos.unlink()
    (protocolo_de_estudio.parent / "anclaje.json").unlink()
    datos["ruta_version"] = "protocolo/protocolo.yaml"
    _agregar_evento(protocolo_de_estudio, "protocolo_aprobado", datos)

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert "en protocolo/protocolo.yaml, no en protocolo/versiones/1.0.0.yaml" in mensaje


def test_p_e10_se_evalua_aunque_haya_p_e00(protocolo_de_estudio: Path) -> None:
    (protocolo_de_estudio.parent / "versiones").mkdir()
    protocolo_de_estudio.write_text("estado: [sin cerrar\n", encoding="utf-8", newline="\n")

    assert _ids(protocolo_de_estudio) == ["P-E00", "P-E10"]


def test_los_eventos_de_otros_tipos_se_ignoran(protocolo_de_estudio: Path) -> None:
    _agregar_evento(protocolo_de_estudio, "nota_libre", {"texto": "prueba"})

    estado = leer_estado_registro(RutasProtocolo.desde(protocolo_de_estudio))

    assert estado.integro
    assert estado.versiones == []
    assert estado.creacion is None
    assert _ids(protocolo_de_estudio) == []


def _datos_creacion() -> dict[str, Any]:
    archivo = {"ruta": "CLAUDE.md", "hash": "sha256:" + "a" * 64}
    return {
        "nombre": "prueba",
        "titulo": "Estudio de prueba",
        "modelo": "claude-opus-5-5",
        "fuente_agente": "git+https://example.org/agentresearch@v0.0.0",
        "archivos": [],
        "instrucciones": [archivo],
        "insumos": [],
    }


def test_el_evento_de_creacion_del_estudio_se_reconoce(protocolo_de_estudio: Path) -> None:
    _agregar_evento(protocolo_de_estudio, "estudio_creado", _datos_creacion())

    estado = leer_estado_registro(RutasProtocolo.desde(protocolo_de_estudio))

    assert estado.integro
    assert estado.creacion is not None
    assert estado.creacion.evento.id == "evt-000001"
    assert estado.creacion.datos.modelo == "claude-opus-5-5"


def test_la_creacion_del_estudio_solo_puede_ser_el_primer_evento(
    protocolo_de_estudio: Path,
) -> None:
    _agregar_evento(protocolo_de_estudio, "estudio_creado", _datos_creacion())
    _agregar_evento(protocolo_de_estudio, "estudio_creado", _datos_creacion())

    estado = leer_estado_registro(RutasProtocolo.desde(protocolo_de_estudio))

    assert estado.problemas == [
        "evt-000002 registra la creación del estudio, que solo puede ser el primer evento "
        "(evt-000001)"
    ]


def test_una_creacion_mal_formada_es_p_e10(protocolo_de_estudio: Path) -> None:
    _agregar_evento(protocolo_de_estudio, "estudio_creado", {"nombre": "prueba"})

    estado = leer_estado_registro(RutasProtocolo.desde(protocolo_de_estudio))

    assert not estado.integro
    assert estado.creacion is None
    assert all("el evento no cumple su esquema" in p for p in estado.problemas)


# --- Decisiones en el registro -----------------------------------------------------


def test_estados_de_las_decisiones(protocolo_de_estudio: Path) -> None:
    rutas = RutasProtocolo.desde(protocolo_de_estudio)
    for datos in (_decision("O1"), _decision("O2"), _decision("O2b", reemplaza="O2")):
        _agregar_evento(protocolo_de_estudio, "decision_propuesta", datos)
    propuesta = RegistroEncadenado(rutas.eventos).leer()[0]
    _agregar_evento(
        protocolo_de_estudio,
        "decision_confirmada",
        {
            "id_decision": "O1",
            "evento_propuesta": propuesta.id,
            "hash_evento_propuesta": propuesta.hash,
            "confirmado_por": {"tipo": "humano", "id": "investigador-1"},
        },
    )

    estado = leer_estado_registro(rutas)

    assert estado.integro
    assert {d.id_decision: d.estado for d in estado.decisiones.values()} == {
        "O1": "confirmada",
        "O2": "reemplazada",
        "O2b": "pendiente",
    }
    assert [d.id_decision for d in estado.pendientes] == ["O2b"]
    assert validar_archivo(protocolo_de_estudio).registro == {
        "ruta": "protocolo/eventos.jsonl",
        "existe": True,
        "integro": True,
        "numero_eventos": 4,
        "anclaje": str(estado.anclaje_actual),
        "anclaje_guardado": str(estado.anclaje_actual),
        "version_registrada": None,
        "hash_registrado": None,
        "decisiones_pendientes": ["O2b"],
        "falta_anclaje": False,
    }


@pytest.mark.parametrize(
    ("propuestas", "fragmento"),
    [
        ([_decision("O1"), _decision("O1")], "vuelve a registrar la decisión O1"),
        ([_decision("O2", reemplaza="O9")], "reemplaza a O9, que no existe"),
        (
            [_decision("O1"), _decision("O2", "O1"), _decision("O3", "O1")],
            "reemplaza a O1, que no existe o ya fue reemplazada",
        ),
    ],
)
def test_p_e10_con_propuestas_incoherentes(
    protocolo_de_estudio: Path, propuestas: list[dict[str, Any]], fragmento: str
) -> None:
    for datos in propuestas:
        _agregar_evento(protocolo_de_estudio, "decision_propuesta", datos)

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E10")

    assert fragmento in mensaje


def test_p_e10_con_confirmaciones_incoherentes(protocolo_de_estudio: Path) -> None:
    rutas = RutasProtocolo.desde(protocolo_de_estudio)
    _agregar_evento(protocolo_de_estudio, "decision_propuesta", _decision("O1"))
    propuesta = RegistroEncadenado(rutas.eventos).leer()[0]
    confirmacion = {
        "id_decision": "O1",
        "evento_propuesta": propuesta.id,
        "hash_evento_propuesta": propuesta.hash,
        "confirmado_por": {"tipo": "humano", "id": "investigador-1"},
    }
    _agregar_evento(protocolo_de_estudio, "decision_confirmada", confirmacion)
    _agregar_evento(protocolo_de_estudio, "decision_confirmada", confirmacion)
    _agregar_evento(
        protocolo_de_estudio,
        "decision_confirmada",
        {**confirmacion, "hash_evento_propuesta": HASH_FICTICIO},
    )

    mensajes = _mensajes(protocolo_de_estudio, "P-E10")

    assert mensajes == [
        "evt-000003 confirma la decisión O1, que no estaba pendiente (confirmada)",
        "evt-000004 confirma la decisión O1, pero no corresponde a la propuesta registrada "
        "en evt-000001",
    ]


# --- P-E09 -----------------------------------------------------------------------


def test_un_protocolo_aprobado_sin_cambios_es_valido(protocolo_de_estudio: Path) -> None:
    datos = _aprobar_a_mano(protocolo_de_estudio)

    resultado = validar_archivo(protocolo_de_estudio)

    assert resultado.hallazgos == []
    assert resultado.estado == "vigente"
    assert resultado.registro is not None
    assert resultado.registro["version_registrada"] == "1.0.0"
    assert resultado.registro["hash_registrado"] == datos["hash_protocolo"]
    assert resultado.hash_archivo == datos["hash_protocolo"]


def test_editar_un_protocolo_vigente_sin_enmienda_produce_p_e09(
    protocolo_de_estudio: Path,
) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    _reemplazar_en(protocolo_de_estudio, "tamano_lote_llm: 25", "tamano_lote_llm: 30")

    resultado = validar_archivo(protocolo_de_estudio)

    [hallazgo] = resultado.hallazgos
    assert hallazgo.id_regla == "P-E09"
    assert hallazgo.ubicacion is None
    assert hallazgo.mensaje == (
        "protocolo/protocolo.yaml cambió desde la versión 1.0.0 registrada en evt-000001; "
        "registre el cambio con `agentresearch protocolo enmendar`"
    )
    assert not resultado.valido


def test_un_cambio_de_solo_comentarios_tambien_produce_p_e09(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    with protocolo_de_estudio.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write("# comentario nuevo\n")

    assert _ids(protocolo_de_estudio) == ["P-E09"]


def test_volver_a_borrador_a_mano_no_evita_p_e09(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    _reemplazar_en(protocolo_de_estudio, "estado: vigente", "estado: borrador")

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E09")

    assert "El archivo dice «borrador», pero el registro contiene una aprobación" in mensaje


def test_p_e09_si_el_protocolo_esta_vigente_sin_registro(protocolo_de_estudio: Path) -> None:
    _reemplazar_en(protocolo_de_estudio, "estado: borrador", "estado: vigente")

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E09")

    assert mensaje.startswith("el protocolo está vigente, pero no existe protocolo/eventos.jsonl")


def test_p_e09_si_el_protocolo_esta_vigente_sin_aprobacion_registrada(
    protocolo_de_estudio: Path,
) -> None:
    _agregar_evento(protocolo_de_estudio, "decision_propuesta", _decision("O1"))
    _reemplazar_en(protocolo_de_estudio, "estado: borrador", "estado: vigente")

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E09")

    assert "protocolo/eventos.jsonl no contiene ninguna aprobación" in mensaje


def test_p_e09_reconoce_una_operacion_interrumpida_y_su_recuperacion(
    protocolo_de_estudio: Path,
) -> None:
    _aprobar_a_mano(protocolo_de_estudio, escribir_protocolo=False)

    [mensaje] = _mensajes(protocolo_de_estudio, "P-E09")
    copia = protocolo_de_estudio.parent / "versiones" / "1.0.0.yaml"
    protocolo_de_estudio.write_bytes(copia.read_bytes())

    assert mensaje == (
        "la aprobación de la versión 1.0.0 registrada en evt-000001 se interrumpió antes de "
        "actualizar protocolo/protocolo.yaml: para completarla, copie "
        "protocolo/versiones/1.0.0.yaml sobre protocolo/protocolo.yaml"
    )
    assert _ids(protocolo_de_estudio) == []


def test_p_e09_se_evalua_aunque_haya_p_e00(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    protocolo_de_estudio.write_text("estado: [sin cerrar\n", encoding="utf-8", newline="\n")

    assert _ids(protocolo_de_estudio) == ["P-E00", "P-E09"]


def test_sin_archivo_de_protocolo_no_se_evalua_p_e09(protocolo_de_estudio: Path) -> None:
    _aprobar_a_mano(protocolo_de_estudio)
    protocolo_de_estudio.unlink()

    assert _ids(protocolo_de_estudio) == ["P-E00"]


# --- Versiones y anclaje ---------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "nivel", "esperada"),
    [
        ("1.0.0", "mayor", "2.0.0"),
        ("1.2.3", "mayor", "2.0.0"),
        ("1.2.3", "menor", "1.3.0"),
        ("1.2.3", "parche", "1.2.4"),
    ],
)
def test_siguiente_version(version: str, nivel: Any, esperada: str) -> None:
    assert siguiente_version(version, nivel) == esperada


def test_texto_del_anclaje_es_json_ordenado_con_lf(protocolo_de_estudio: Path) -> None:
    rutas = RutasProtocolo.desde(protocolo_de_estudio)
    anclaje = Anclaje(2, HASH_FICTICIO)

    texto = texto_anclaje(rutas, anclaje)

    assert texto.endswith(b"}\n")
    assert b"\r" not in texto
    assert json.loads(texto) == {
        "hash_ultimo": HASH_FICTICIO,
        "numero_eventos": 2,
        "registro": "protocolo/eventos.jsonl",
    }
    assert list(json.loads(texto)) == sorted(json.loads(texto))
