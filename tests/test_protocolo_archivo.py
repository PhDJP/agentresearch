"""Pruebas de lectura y escritura del protocolo en YAML, conservando comentarios."""

from pathlib import Path

import pytest
from pydantic_core import ErrorDetails
from ruamel.yaml.scalarbool import ScalarBoolean
from ruamel.yaml.scalarfloat import ScalarFloat
from ruamel.yaml.scalarint import ScalarInt
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from agentresearch.protocolo import (
    ErrorLecturaProtocolo,
    ProblemaLectura,
    Protocolo,
    actualizar_documento,
    cargar_protocolo,
    escribir_protocolo,
    leer_protocolo,
    texto_plantilla,
    texto_protocolo,
)
from agentresearch.protocolo.archivo import _mensaje_de_esquema, a_python, formatear_ubicacion
from agentresearch.protocolo.modelo import Criterio

RUTA_PROTOCOLO_SINTETICO = Path(__file__).parent / "datos" / "protocolo_sintetico.yaml"

PARRAFO_LARGO = (
    "La deshidratación del fruto de zarambo se ha estudiado en publicaciones dispersas de "
    "ciencias agrarias, ingeniería de alimentos y química analítica; ninguna revisión previa "
    "reúne los métodos de secado, las condiciones de operación ni las propiedades evaluadas "
    "del producto seco, y por eso un mapeo sistemático permitiría identificar vacíos, "
    "agrupar la evidencia según la escala del estudio (laboratorio, piloto o industrial) y "
    "orientar la investigación futura sobre el aprovechamiento de este fruto ficticio. "
) * 3


def _lineas_de_comentario(texto: str) -> list[str]:
    return [linea for linea in texto.splitlines() if linea.lstrip().startswith("#")]


def _problema_unico(texto: str) -> ProblemaLectura:
    with pytest.raises(ErrorLecturaProtocolo) as informacion:
        cargar_protocolo(texto)
    assert len(informacion.value.problemas) == 1
    return informacion.value.problemas[0]


# --- Plantilla -----------------------------------------------------------------


def test_la_plantilla_cumple_el_esquema() -> None:
    documento = cargar_protocolo(texto_plantilla())

    assert documento.protocolo.estado == "borrador"
    assert documento.protocolo.seleccion.regla_combinacion.avanzan == ["A", "B", "C", "D", "E"]
    assert documento.protocolo.seleccion.piloto.umbral_kappa == pytest.approx(0.61)
    assert documento.protocolo.seleccion.tamano_lote_llm == 25


def test_la_plantilla_comenta_cada_seccion_principal() -> None:
    lineas = texto_plantilla().splitlines()
    claves_de_primer_nivel = [
        indice for indice, linea in enumerate(lineas) if linea and linea[0].isalpha()
    ]

    for indice in claves_de_primer_nivel:
        clave = lineas[indice].split(":")[0]
        if clave in ("version_esquema", "pregunta_general"):
            continue  # cubiertas por el comentario de cabecera y el de objetivos
        assert lineas[indice - 1].startswith("# "), f"falta el comentario de {clave}"


def test_la_plantilla_esta_en_utf8_con_lf() -> None:
    texto = texto_plantilla()

    assert "\r" not in texto
    assert "ítem" in texto


# --- Ida y vuelta --------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [texto_plantilla(), RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8")],
    ids=["plantilla", "sintetico"],
)
def test_leer_y_escribir_sin_cambios_es_identico(texto: str) -> None:
    assert texto_protocolo(cargar_protocolo(texto)) == texto


def test_escribir_produce_un_archivo_identico_byte_a_byte(tmp_path: Path) -> None:
    destino = tmp_path / "protocolo.yaml"

    escribir_protocolo(leer_protocolo(RUTA_PROTOCOLO_SINTETICO), destino)

    assert destino.read_bytes() == RUTA_PROTOCOLO_SINTETICO.read_bytes()


def test_escribir_usa_utf8_y_lf(tmp_path: Path) -> None:
    destino = tmp_path / "protocolo.yaml"

    escribir_protocolo(cargar_protocolo(texto_plantilla()), destino)

    contenido = destino.read_bytes()
    assert b"\r\n" not in contenido
    assert "ítem".encode() in contenido


def test_actualizar_sin_cambios_no_altera_el_texto() -> None:
    documento = cargar_protocolo(texto_plantilla())

    actualizar_documento(documento, documento.protocolo.model_copy(deep=True))

    assert texto_protocolo(documento) == texto_plantilla()


def test_un_parrafo_largo_con_tildes_queda_en_una_linea_y_vuelve_igual(tmp_path: Path) -> None:
    documento = cargar_protocolo(texto_plantilla())
    actualizar_documento(
        documento, documento.protocolo.model_copy(update={"justificacion": PARRAFO_LARGO})
    )
    destino = tmp_path / "protocolo.yaml"

    escribir_protocolo(documento, destino)

    texto = destino.read_text(encoding="utf-8")
    [linea] = [linea for linea in texto.splitlines() if linea.startswith("justificacion:")]
    assert PARRAFO_LARGO.strip() in linea
    assert leer_protocolo(destino).protocolo.justificacion == PARRAFO_LARGO
    assert texto_protocolo(leer_protocolo(destino)) == texto
    assert _lineas_de_comentario(texto) == _lineas_de_comentario(texto_plantilla())


def test_actualizar_conserva_todos_los_comentarios() -> None:
    documento = cargar_protocolo(texto_plantilla())
    protocolo = documento.protocolo
    metadatos = protocolo.metadatos.model_copy(update={"titulo": "Secado del zarambo"})
    actualizar_documento(
        documento,
        protocolo.model_copy(update={"metadatos": metadatos, "estado": "vigente"}),
    )

    texto = texto_protocolo(documento)

    assert _lineas_de_comentario(texto) == _lineas_de_comentario(texto_plantilla())
    assert 'titulo: "Secado del zarambo"' in texto  # conserva las comillas dobles
    assert "estado: vigente\n" in texto


def test_actualizar_conserva_un_umbral_entero() -> None:
    texto = texto_plantilla().replace("umbral_kappa: 0.61", "umbral_kappa: 1")
    documento = cargar_protocolo(texto)

    actualizar_documento(documento, documento.protocolo.model_copy(deep=True))

    assert "umbral_kappa: 1\n" in texto_protocolo(documento)


def test_actualizar_no_agrega_valores_por_defecto_implicitos() -> None:
    texto = texto_plantilla().replace('      orcid: ""\n      rol: ""\n', "")
    documento = cargar_protocolo(texto)

    actualizar_documento(documento, documento.protocolo.model_copy(deep=True))

    assert texto_protocolo(documento) == texto


def test_actualizar_agrega_un_campo_asignado_que_no_estaba_en_el_yaml() -> None:
    texto = texto_plantilla().replace('      orcid: ""\n', "")
    documento = cargar_protocolo(texto)
    metadatos = documento.protocolo.metadatos
    autor = metadatos.autores[0].model_copy(update={"orcid": "0000-0000-0000-0000"})
    actualizar_documento(
        documento,
        documento.protocolo.model_copy(
            update={"metadatos": metadatos.model_copy(update={"autores": [autor]})}
        ),
    )

    texto_nuevo = texto_protocolo(documento)

    assert "      orcid: 0000-0000-0000-0000\n" in texto_nuevo
    assert cargar_protocolo(texto_nuevo).protocolo.metadatos.autores[0].orcid == (
        "0000-0000-0000-0000"
    )


def test_las_listas_con_id_se_fusionan_por_id_y_no_por_posicion() -> None:
    texto = texto_plantilla().replace(
        '    - id: CI1\n      texto: ""',
        '    - id: CI1\n      texto: ""  # nota del investigador sobre CI1',
    )
    documento = cargar_protocolo(texto)
    ci1 = documento.protocolo.criterios.inclusion[0]
    ci2 = Criterio(
        id="CI2", texto="Está en español.", fase="ambas", tipo="idioma", ejemplos_si=["Un artículo"]
    )
    criterios = documento.protocolo.criterios.model_copy(update={"inclusion": [ci2, ci1]})

    actualizar_documento(documento, documento.protocolo.model_copy(update={"criterios": criterios}))

    resultado = texto_protocolo(documento)
    posicion_ci2 = resultado.index("- id: CI2")
    posicion_ci1 = resultado.index("- id: CI1")
    posicion_nota = resultado.index("# nota del investigador sobre CI1")
    assert posicion_ci2 < posicion_ci1 < posicion_nota
    assert (
        resultado.index("\n", posicion_ci1) < posicion_nota < resultado.index("fase:", posicion_ci1)
    )
    assert "      ejemplos_si: [Un artículo]\n" in resultado
    recargado = cargar_protocolo(resultado).protocolo
    assert [c.id for c in recargado.criterios.inclusion] == ["CI2", "CI1"]


def test_eliminar_un_elemento_por_id_conserva_los_demas() -> None:
    documento = cargar_protocolo(RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8"))
    preguntas = [p for p in documento.protocolo.preguntas if p.id != "PI2"]

    actualizar_documento(documento, documento.protocolo.model_copy(update={"preguntas": preguntas}))

    recargado = cargar_protocolo(texto_protocolo(documento)).protocolo
    assert [p.id for p in recargado.preguntas] == ["PI1", "PI3"]
    assert recargado.preguntas[1].derivada_de == [["F1", "F2"]]


def test_las_listas_sin_id_se_fusionan_por_posicion() -> None:
    documento = cargar_protocolo(texto_plantilla())
    busqueda = documento.protocolo.busqueda
    idiomas = busqueda.idiomas.model_copy(update={"valores": ["en", "es"]})
    actualizar_documento(
        documento,
        documento.protocolo.model_copy(
            update={"busqueda": busqueda.model_copy(update={"idiomas": idiomas})}
        ),
    )

    assert "valores: [en, es]\n" in texto_protocolo(documento)

    busqueda = documento.protocolo.busqueda
    idiomas = busqueda.idiomas.model_copy(update={"valores": ["es"]})
    actualizar_documento(
        documento,
        documento.protocolo.model_copy(
            update={"busqueda": busqueda.model_copy(update={"idiomas": idiomas})}
        ),
    )

    assert "valores: [es]\n" in texto_protocolo(documento)


def test_una_lista_nueva_de_mapas_se_escribe_en_bloque() -> None:
    documento = cargar_protocolo(texto_plantilla())
    busqueda_manual = documento.protocolo.estrategias.busqueda_manual.model_copy(
        update={"fuentes": ["Revista ficticia de secado"]}
    )
    calidad = documento.protocolo.calidad.model_copy(update={"preguntas": ["¿Describe el método?"]})
    estrategias = documento.protocolo.estrategias.model_copy(
        update={"busqueda_manual": busqueda_manual}
    )
    documento.protocolo.metadatos.autores.append(
        documento.protocolo.metadatos.autores[0].model_copy(update={"nombre": "Otra persona"})
    )

    actualizar_documento(
        documento,
        documento.protocolo.model_copy(update={"estrategias": estrategias, "calidad": calidad}),
    )

    texto = texto_protocolo(documento)
    assert "fuentes: [Revista ficticia de secado]" in texto
    assert "    - nombre: Otra persona\n" in texto
    assert cargar_protocolo(texto).protocolo.calidad.preguntas == ["¿Describe el método?"]


def test_actualizar_elimina_las_claves_ausentes_del_modelo() -> None:
    documento = cargar_protocolo(texto_plantilla())
    datos = documento.protocolo.model_dump(exclude_unset=True)
    del datos["metadatos"]["registro"]

    actualizar_documento(documento, Protocolo.model_validate(datos))

    assert "registro:" not in texto_protocolo(documento)


# --- Errores de lectura (P-E00) ------------------------------------------------


def test_archivo_inexistente(tmp_path: Path) -> None:
    with pytest.raises(ErrorLecturaProtocolo, match="no existe"):
        leer_protocolo(tmp_path / "no_existe.yaml")


def test_ruta_que_no_es_un_archivo(tmp_path: Path) -> None:
    with pytest.raises(ErrorLecturaProtocolo, match="no se pudo leer"):
        leer_protocolo(tmp_path)


def test_archivo_que_no_es_utf8(tmp_path: Path) -> None:
    archivo = tmp_path / "protocolo.yaml"
    archivo.write_bytes("titulo: áé".encode("latin-1"))

    with pytest.raises(ErrorLecturaProtocolo, match="UTF-8"):
        leer_protocolo(archivo)


def test_archivo_vacio() -> None:
    assert "vacío" in _problema_unico("").mensaje


def test_raiz_que_no_es_un_mapa() -> None:
    assert "raíz" in _problema_unico("- uno\n- dos\n").mensaje


def test_yaml_mal_formado_informa_linea_y_columna() -> None:
    problema = _problema_unico("version_esquema: 1\nestado: borrador: otro\n")

    assert (problema.linea, problema.columna) == (2, 17)
    assert "YAML mal formado en la línea 2, columna 17" in problema.mensaje


def test_yaml_con_tabulador_informa_linea_y_columna() -> None:
    problema = _problema_unico("version_esquema: 1\npreguntas:\n\t- id: PI1\n")

    assert problema.linea == 3
    assert problema.columna == 1


def test_caracter_no_permitido_sin_posicion_de_problema() -> None:
    problema = _problema_unico("version_esquema: 1\nestado: \x07\n")

    assert problema.mensaje.startswith("YAML mal formado")
    assert problema.linea is None


def test_clave_duplicada_informa_la_linea() -> None:
    problema = _problema_unico("version_esquema: 1\nestado: borrador\nestado: vigente\n")

    assert problema.linea == 3
    assert "clave duplicada" in problema.mensaje


@pytest.mark.parametrize("version", ["2", "true", '"1"'])
def test_version_de_esquema_no_soportada(version: str) -> None:
    texto = texto_plantilla().replace("version_esquema: 1", f"version_esquema: {version}")

    problema = _problema_unico(texto)

    assert "versión de esquema no soportada" in problema.mensaje
    assert problema.ubicacion == "version_esquema"
    assert problema.linea == 4


def test_falta_la_version_de_esquema() -> None:
    problema = _problema_unico(texto_plantilla().replace("version_esquema: 1\n", ""))

    assert problema.ubicacion == "version_esquema"
    assert problema.mensaje == "falta este campo obligatorio"


def test_error_de_esquema_informa_ubicacion_y_linea() -> None:
    texto = texto_plantilla().replace("tamano_lote_llm: 25", 'tamano_lote_llm: "25"')

    problema = _problema_unico(texto)

    assert problema.ubicacion == "seleccion.tamano_lote_llm"
    assert problema.mensaje == "se esperaba un número entero; valor recibido: '25'"
    linea = texto.splitlines()[problema.linea - 1] if problema.linea else ""
    assert linea.strip().startswith("tamano_lote_llm:")


def test_clave_no_permitida() -> None:
    texto = texto_plantilla().replace("estado: borrador", "estado: borrador\nestatus: x")

    problema = _problema_unico(texto)

    assert problema.ubicacion == "estatus"
    assert problema.mensaje == "clave no permitida por el esquema"


def test_valor_fuera_de_la_enumeracion_lista_los_permitidos() -> None:
    problema = _problema_unico(texto_plantilla().replace("estado: borrador", "estado: listo"))

    assert "se admite 'borrador' o 'vigente'" in problema.mensaje


def test_version_de_protocolo_con_formato_invalido() -> None:
    texto = texto_plantilla().replace('version_protocolo: "0.1.0"', 'version_protocolo: "1.0"')

    assert "no cumple el formato exigido" in _problema_unico(texto).mensaje


def test_cruce_demasiado_corto() -> None:
    texto = texto_plantilla().replace("  cruces:\n    - [F1, F2]", "  cruces:\n    - [F1]")

    problema = _problema_unico(texto)

    assert problema.ubicacion == "analisis.cruces[0]"
    assert "al menos 2 elementos" in problema.mensaje


def test_ubicacion_de_un_elemento_de_lista_ausente_usa_la_del_padre() -> None:
    texto = texto_plantilla().replace("avanzan: [A, B, C, D, E]", "avanzan: [A, G]")

    problema = _problema_unico(texto)

    assert problema.ubicacion == "seleccion.regla_combinacion.avanzan[1]"
    assert problema.linea is not None


def test_varios_errores_de_esquema_se_reportan_juntos() -> None:
    texto = (
        texto_plantilla()
        .replace("estado: borrador", "estado: x")
        .replace("tamano_lote_llm: 25", "tamano_lote_llm: y")
    )

    with pytest.raises(ErrorLecturaProtocolo) as informacion:
        cargar_protocolo(texto)

    ubicaciones = {problema.ubicacion for problema in informacion.value.problemas}
    assert ubicaciones == {"estado", "seleccion.tamano_lote_llm"}


def test_mensaje_generico_para_otros_errores_de_esquema() -> None:
    texto = texto_plantilla().replace("umbral_kappa: 0.61", "umbral_kappa: [0.61]")

    assert "se esperaba un número" in _problema_unico(texto).mensaje


def test_mensaje_de_esquema_desconocido_conserva_el_tipo_y_el_detalle() -> None:
    detalle: ErrorDetails = {
        "type": "tipo_nuevo",
        "loc": ("estado",),
        "msg": "detalle original",
        "input": "x",
    }

    mensaje = _mensaje_de_esquema(detalle)

    assert mensaje == "no cumple el esquema (tipo_nuevo: detalle original); valor recibido: 'x'"


def test_valor_recibido_largo_se_resume() -> None:
    texto = texto_plantilla().replace("tamano_lote_llm: 25", f'tamano_lote_llm: "{"x" * 100}"')

    mensaje = _problema_unico(texto).mensaje

    assert mensaje.endswith("…")
    assert len(mensaje) < 120


# --- Utilidades ----------------------------------------------------------------


def test_a_python_convierte_los_escalares_de_ruamel() -> None:
    convertido = a_python(
        {
            "texto": DoubleQuotedScalarString("hola"),
            "entero": ScalarInt(5),
            "real": ScalarFloat(0.5),
            "logico": ScalarBoolean(True),
            "tupla": (1, 2),
        }
    )

    assert convertido == {
        "texto": "hola",
        "entero": 5,
        "real": 0.5,
        "logico": True,
        "tupla": [1, 2],
    }
    assert type(convertido["texto"]) is str
    assert type(convertido["entero"]) is int
    assert type(convertido["real"]) is float
    assert type(convertido["logico"]) is bool


def test_formatear_ubicacion() -> None:
    assert (
        formatear_ubicacion(["criterios", "inclusion", 0, "fase"]) == "criterios.inclusion[0].fase"
    )
    assert formatear_ubicacion([]) == ""
