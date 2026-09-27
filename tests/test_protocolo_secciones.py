"""Pruebas de la escritura de una sección del protocolo (`protocolo escribir`, ADR-0007)."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from agentresearch.cli import ejecutar_protocolo_escribir, main
from agentresearch.protocolo import leer_protocolo, texto_plantilla, validar_archivo
from agentresearch.protocolo.aprobacion import ErrorCicloDeVida, enmendar
from agentresearch.protocolo.archivo import texto_protocolo
from agentresearch.protocolo.secciones import SECCIONES, escribir_seccion
from agentresearch.trazabilidad import hash_archivo

from .apoyo import TerminalSimulada, aprobar_protocolo, reloj_incremental

PARCHE_TEXTO = "agentresearch.protocolo.secciones.texto_protocolo"

CRITERIOS_NUEVOS = """\
criterios:
  inclusion:
    - id: CI1
      texto: "Estudia el secado del fruto de zarambo."
      fase: titulo_resumen
      tipo: tema
      ejemplos_si: [Secado solar del zarambo]
      ejemplos_no: [Secado de otro fruto]
    - id: CI2
      texto: "Reporta al menos una propiedad del producto seco."
      fase: texto_completo
      tipo: tema
      ejemplos_si: [Humedad final]
      ejemplos_no: [Solo costos]
  exclusion:
    - id: CE1
      texto: "No es un estudio primario."
      fase: ambas
      tipo: tipo_documento
      ejemplos_si: [Una revisión]
      ejemplos_no: [Un experimento]
"""


def _fragmento(tmp_path: Path, texto: str, nombre: str = "seccion.yaml") -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(texto, encoding="utf-8", newline="\n")
    return ruta


def _criterios_actuales(ruta: Path) -> dict[str, Any]:
    return leer_protocolo(ruta).protocolo.criterios.model_dump()


@pytest.fixture
def protocolo_desde_plantilla(tmp_path: Path) -> Path:
    """Estudio con el protocolo recién creado desde la plantilla, como lo deja `nuevo-estudio`."""
    ruta = tmp_path / "estudio" / "protocolo" / "protocolo.yaml"
    ruta.parent.mkdir(parents=True)
    ruta.write_bytes(texto_plantilla().encode("utf-8"))
    return ruta


# --- Escritura en borrador ------------------------------------------------------------


def test_escribe_una_seccion_y_valida_el_resultado(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    antes = leer_protocolo(protocolo_de_estudio).protocolo

    resultado = escribir_seccion(
        protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS)
    )

    despues = leer_protocolo(protocolo_de_estudio).protocolo
    assert resultado.cambio is True
    assert resultado.ruta_protocolo == "protocolo/protocolo.yaml"
    assert resultado.hash_protocolo == hash_archivo(protocolo_de_estudio)
    assert resultado.hash_anterior != resultado.hash_protocolo
    assert resultado.estado == "borrador"
    assert resultado.pendiente_de_enmienda is False
    assert [c.id for c in despues.criterios.inclusion] == ["CI1", "CI2"]
    assert despues.criterios.exclusion[0].tipo == "tipo_documento"
    # Las demás secciones no cambian.
    assert despues.model_dump(exclude={"criterios"}) == antes.model_dump(exclude={"criterios"})
    assert resultado.validacion.valido


def test_lo_que_no_esta_en_el_fragmento_se_elimina(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    fragmento = CRITERIOS_NUEVOS.split("  exclusion:")[0] + "  exclusion: []\n"

    escribir_seccion(protocolo_de_estudio, "criterios", _fragmento(tmp_path, fragmento))

    assert _criterios_actuales(protocolo_de_estudio)["exclusion"] == []


def test_lo_nuevo_conserva_las_comillas_del_fragmento(
    protocolo_desde_plantilla: Path, tmp_path: Path
) -> None:
    escribir_seccion(protocolo_desde_plantilla, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS))

    texto = protocolo_desde_plantilla.read_text(encoding="utf-8")
    assert '      texto: "Reporta al menos una propiedad del producto seco."\n' in texto
    assert "      ejemplos_si: [Humedad final]\n" in texto


def test_vaciar_una_lista_desde_la_plantilla_conserva_los_comentarios_de_seccion(
    protocolo_desde_plantilla: Path, tmp_path: Path
) -> None:
    fragmento = CRITERIOS_NUEVOS.split("  exclusion:")[0] + "  exclusion: []\n"

    escribir_seccion(protocolo_desde_plantilla, "criterios", _fragmento(tmp_path, fragmento))

    def comentarios(texto: str) -> list[str]:
        return [linea for linea in texto.splitlines() if linea.startswith("#")]

    texto = protocolo_desde_plantilla.read_text(encoding="utf-8")
    assert comentarios(texto) == comentarios(texto_plantilla())
    lineas = texto.splitlines()
    assert lineas[lineas.index("seleccion:") - 1].startswith("# Revisores")


def test_escribe_una_seccion_de_texto(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    fragmento = _fragmento(tmp_path, 'justificacion: "Nadie ha mapeado el secado del zarambo."\n')

    escribir_seccion(protocolo_de_estudio, "justificacion", fragmento)

    protocolo = leer_protocolo(protocolo_de_estudio).protocolo
    assert protocolo.justificacion == "Nadie ha mapeado el secado del zarambo."


def test_una_seccion_identica_no_toca_el_archivo(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    escribir_seccion(protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS))
    contenido = protocolo_de_estudio.read_bytes()

    resultado = escribir_seccion(
        protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS)
    )

    assert resultado.cambio is False
    assert resultado.hash_anterior == resultado.hash_protocolo
    assert protocolo_de_estudio.read_bytes() == contenido


def test_las_secciones_siguen_el_orden_de_protocolo() -> None:
    assert SECCIONES[0] == "metadatos"
    assert SECCIONES[-1] == "analisis"
    assert "estado" not in SECCIONES
    assert "version_esquema" not in SECCIONES


# --- Rechazos, sin escribir nada ----------------------------------------------------


def _rechazo(ruta: Path, seccion: str, fragmento: Path) -> list[str]:
    contenido = ruta.read_bytes()
    with pytest.raises(ErrorCicloDeVida) as informacion:
        escribir_seccion(ruta, seccion, fragmento)
    assert ruta.read_bytes() == contenido
    return informacion.value.errores


def test_rechaza_una_seccion_que_asigna_el_paquete(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    [error] = _rechazo(protocolo_de_estudio, "estado", _fragmento(tmp_path, "estado: vigente\n"))

    assert "la sección «estado» no se escribe con este comando" in error


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("criterios: {}\nfuentes: []\n", "tiene: criterios, fuentes"),
        ("fuentes: []\n", "debe tener una sola clave de primer nivel, «criterios»"),
        ("criterios: [\n", "YAML mal formado"),
        ("criterios: 1\ncriterios: 2\n", "clave duplicada"),
        ("- criterios\n", "la raíz del documento debe ser un mapa"),
        ("", "el archivo está vacío"),
    ],
    ids=["dos-claves", "otra-clave", "mal-formado", "duplicada", "lista", "vacio"],
)
def test_rechaza_un_fragmento_invalido(
    protocolo_de_estudio: Path, tmp_path: Path, texto: str, esperado: str
) -> None:
    errores = _rechazo(protocolo_de_estudio, "criterios", _fragmento(tmp_path, texto))

    assert any(esperado in error for error in errores), errores


def test_rechaza_un_fragmento_que_no_es_utf8(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    fragmento = tmp_path / "seccion.yaml"
    fragmento.write_bytes('justificacion: "secado\xf1"\n'.encode("latin-1"))

    [error] = _rechazo(protocolo_de_estudio, "justificacion", fragmento)

    assert "no está codificado en UTF-8" in error


def test_rechaza_un_fragmento_inexistente(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    [error] = _rechazo(protocolo_de_estudio, "criterios", tmp_path / "no-existe.yaml")

    assert "no se pudo leer el fragmento" in error


def test_rechaza_una_seccion_que_no_cumple_el_esquema(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    texto = CRITERIOS_NUEVOS.replace("fase: texto_completo", "fase: al_final")

    errores = _rechazo(protocolo_de_estudio, "criterios", _fragmento(tmp_path, texto))

    assert any(
        "la sección no cumple el esquema (P-E00): criterios.inclusion[1].fase" in error
        for error in errores
    ), errores


def test_rechaza_cambiar_la_version_del_protocolo(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    metadatos = leer_protocolo(protocolo_de_estudio).protocolo.metadatos.model_dump(
        exclude_unset=True
    )
    metadatos["version_protocolo"] = "0.2.0"
    fragmento = _fragmento(tmp_path, "metadatos: " + json.dumps(metadatos) + "\n")

    [error] = _rechazo(protocolo_de_estudio, "metadatos", fragmento)

    assert "metadatos.version_protocolo no se escribe con este comando (es 0.1.0)" in error


def test_rechaza_un_protocolo_ilegible(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    protocolo_de_estudio.write_text("version_esquema: 1\nestado: [\n", encoding="utf-8")

    errores = _rechazo(protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS))

    assert errores[0].startswith("no se pudo leer protocolo/protocolo.yaml (P-E00): YAML mal")
    assert errores[-1] == "corrija el archivo a mano antes de escribir una sección"


def test_rechaza_con_el_registro_roto(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    (protocolo_de_estudio.parent / "anclaje.json").write_text("{}", encoding="utf-8")

    [error] = _rechazo(protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS))

    assert error.startswith("el registro de eventos no es íntegro (P-E10): falta ")


def test_rechaza_con_una_operacion_interrumpida(protocolo_de_estudio: Path, tmp_path: Path) -> None:
    borrador = protocolo_de_estudio.read_bytes()
    aprobar_protocolo(protocolo_de_estudio)
    protocolo_de_estudio.write_bytes(borrador)  # como si la aprobación no hubiera llegado al YAML

    [error] = _rechazo(protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS))

    assert "se interrumpió antes de actualizar protocolo/protocolo.yaml" in error
    assert "copie protocolo/versiones/1.0.0.yaml sobre protocolo/protocolo.yaml" in error


def test_rechaza_si_el_archivo_cambia_mientras_se_escribe(
    protocolo_de_estudio: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    texto_real = texto_protocolo

    def texto_y_edicion_ajena(documento: Any) -> str:
        texto = texto_real(documento)
        with protocolo_de_estudio.open("a", encoding="utf-8") as archivo:
            archivo.write("# edición ajena\n")
        return texto

    monkeypatch.setattr(PARCHE_TEXTO, texto_y_edicion_ajena)
    fragmento = _fragmento(tmp_path, CRITERIOS_NUEVOS)

    with pytest.raises(ErrorCicloDeVida, match="cambió mientras se escribía"):
        escribir_seccion(protocolo_de_estudio, "criterios", fragmento)

    assert protocolo_de_estudio.read_text(encoding="utf-8").endswith("# edición ajena\n")


def test_rechaza_un_texto_nuevo_que_no_corresponde_al_modelo(
    protocolo_de_estudio: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    texto_real = texto_protocolo
    monkeypatch.setattr(
        PARCHE_TEXTO,
        lambda documento: texto_real(documento).replace("tipo_documento", "tema"),
    )

    errores = _rechazo(protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS))

    assert errores == ["error interno: el texto nuevo del protocolo no es el esperado"]


# --- Protocolo vigente: la vía para preparar una enmienda ---------------------------


def test_con_el_protocolo_vigente_escribe_y_queda_p_e09_hasta_la_enmienda(
    protocolo_de_estudio: Path, tmp_path: Path
) -> None:
    aprobar_protocolo(protocolo_de_estudio)

    resultado = escribir_seccion(
        protocolo_de_estudio, "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS)
    )

    assert resultado.cambio is True
    assert resultado.estado == "vigente"
    assert resultado.version_protocolo == "1.0.0"
    assert resultado.pendiente_de_enmienda is True
    assert [h.id_regla for h in resultado.validacion.errores] == ["P-E09"]

    enmienda = enmendar(
        protocolo_de_estudio,
        "mayor",
        "investigador-1",
        TerminalSimulada(["enmendar 2.0.0"]),
        justificacion="Se precisan los criterios.",
        efecto_esperado="Cambia qué estudios se incluyen.",
        reloj=reloj_incremental(),
    )

    assert enmienda.version_protocolo == "2.0.0"
    assert validar_archivo(protocolo_de_estudio).valido


# --- CLI ---------------------------------------------------------------------------


def test_cli_escribir_en_texto(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    aprobar_protocolo(protocolo_de_estudio)

    codigo = ejecutar_protocolo_escribir(
        "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS), protocolo_de_estudio
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "sección «criterios» escrita en protocolo/protocolo.yaml" in salida
    assert f"protocolo: vigente, versión 1.0.0, hash {hash_archivo(protocolo_de_estudio)}" in salida
    assert "error P-E09" in salida
    assert "validación: 1 error, 0 advertencias" in salida
    assert "hasta que el investigador registre la enmienda en su terminal" in salida


def test_cli_escribir_sin_cambios(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fragmento = _fragmento(tmp_path, CRITERIOS_NUEVOS)
    ejecutar_protocolo_escribir("criterios", fragmento, protocolo_de_estudio)
    capsys.readouterr()

    codigo = ejecutar_protocolo_escribir("criterios", fragmento, protocolo_de_estudio)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "sin cambios: la sección «criterios» ya tenía ese contenido" in salida
    assert "validación: sin errores ni advertencias" in salida


def test_cli_escribir_avisa_de_ecuaciones_desactualizadas(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (protocolo_de_estudio.parent / "ecuaciones.md").write_text(
        "- Hash del protocolo: sha256:" + "0" * 64 + "\n", encoding="utf-8"
    )

    ejecutar_protocolo_escribir(
        "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS), protocolo_de_estudio
    )

    assert "nota: ecuaciones desactualizadas" in capsys.readouterr().out


def test_cli_escribir_en_json(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_escribir(
        "criterios", _fragmento(tmp_path, CRITERIOS_NUEVOS), protocolo_de_estudio, como_json=True
    )

    salida = capsys.readouterr().out
    datos = json.loads(salida)
    assert salida.isascii()
    assert codigo == 0
    assert datos["comando"] == "protocolo escribir"
    assert datos["exito"] is True
    assert datos["resultado"]["seccion"] == "criterios"
    assert datos["resultado"]["cambio"] is True
    assert datos["resultado"]["pendiente_de_enmienda"] is False
    assert datos["resultado"]["validacion"]["valido"] is True


def test_cli_escribir_rechazado_en_json(
    protocolo_de_estudio: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = ejecutar_protocolo_escribir(
        "criterios", _fragmento(tmp_path, "fuentes: []\n"), protocolo_de_estudio, como_json=True
    )

    datos = json.loads(capsys.readouterr().out)
    assert codigo == 1
    assert datos["exito"] is False
    assert datos["resultado"] is None
    assert "debe tener una sola clave" in datos["errores"][0]


def test_main_escribir(
    protocolo_de_estudio: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fragmento = _fragmento(tmp_path, CRITERIOS_NUEVOS)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agentresearch",
            "protocolo",
            "escribir",
            "criterios",
            "--archivo",
            str(fragmento),
            "--protocolo",
            str(protocolo_de_estudio),
        ],
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 0
    assert "sección «criterios» escrita" in capsys.readouterr().out


def test_main_escribir_rechaza_una_seccion_desconocida(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["agentresearch", "protocolo", "escribir", "estado", "--archivo", "x.yaml"]
    )

    with pytest.raises(SystemExit) as salida:
        main()

    assert salida.value.code == 2
    assert "'estado'" in capsys.readouterr().err
