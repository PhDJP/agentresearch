"""Utilidades de las pruebas de `importar registrar` e `importar historial` (todo sintético)."""

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agentresearch.importacion.registrar import ResultadoRegistro, registrar_busqueda
from agentresearch.protocolo.archivo import decodificar_protocolo, leer_bytes_protocolo
from agentresearch.protocolo.ecuaciones import generar_ecuaciones

from .apoyo import TerminalSimulada, aprobar_protocolo, reloj_incremental
from .apoyo_importacion import escribir
from .conftest import RUTA_PROTOCOLO_SINTETICO

BASE_COMPLETA = (
    "{tipo: institucion, detalle: Biblioteca ficticia, medio: correo, fecha: 2026-10-05}"
)
CONFIGURACION_COMPLETA = f"""
fuentes:
  scopus:
    campos:
      id_fuente:
        base: {BASE_COMPLETA}
      titulo:
        base: {BASE_COMPLETA}
      autores:
        base: {BASE_COMPLETA}
      doi:
        base: {BASE_COMPLETA}
"""
RESUMEN = "Resumen ficticio que nunca se publica."
FUENTE_SCOPUS = (
    '  - id: scopus\n    tipo: exportacion\n    cobertura: "Desde 1960"\n    limites: "Ninguno"\n'
)


def sin_comprobar_git(_raiz: Path, _rutas: object) -> list[str]:
    """Comprobador de ignorados que acepta todo (las pruebas de Git usan el real)."""
    return []


def desfase_menos_cinco(_momento: datetime) -> timedelta:
    return timedelta(hours=-5)


def reloj_de_registro() -> Any:
    """Un reloj que avanza un segundo por llamada desde el 2026-10-14 15:00 UTC."""
    return reloj_incremental(datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC))


def ris(numero: int, *, eid: str | None = None, doi: str | None = None) -> str:
    """Un registro RIS de Scopus ficticio."""
    lineas = [
        "TY  - JOUR",
        "AU  - Cristal, A.",
        f"TI  - Abejas de cristal {numero}",
        "PY  - 2024",
        f"DO  - {doi or f'10.5555/ABEJA.{numero}'}",
        f"AB  - {RESUMEN}",
        "DB  - Scopus",
        f"N1  - EID: {eid or f'2-s2.0-{numero:012d}'}",
        "ER  - ",
    ]
    return "\n".join(lineas) + "\n\n"


def _contar_registros(archivo: Path) -> int:
    try:
        return archivo.read_bytes().decode("utf-8", errors="ignore").count("TY  -")
    except OSError:
        return 0


@dataclass
class Estudio:
    """Un estudio sintético con el protocolo aprobado y una configuración de publicación."""

    raiz: Path
    protocolo: Path
    descargas: Path

    def archivo_ris(self, nombre: str, *numeros: int) -> Path:
        return escribir(self.descargas / nombre, "".join(ris(n) for n in numeros))

    def busqueda(self, archivos: list[Path], **cambios: Any) -> Path:
        """Escribe el archivo de la búsqueda en `.borradores/` y devuelve su ruta."""
        datos: dict[str, Any] = {
            "fuente": "scopus",
            "plataforma": "Scopus (scopus.com)",
            "institucion_acceso": "Universidad ficticia",
            "cobertura": "Todo el contenido",
            "lematizacion": None,
            "filtros": ["Document Types: Article"],
            "ecuacion_ejecutada": self.ecuacion_esperada("scopus"),
            "justificacion_ecuacion": "",
            "resultados_interfaz": sum(_contar_registros(a) for a in archivos),
            "justificacion_diferencia": "",
            "formato": "ris",
            "mapeo": None,
            "archivos": [str(a) for a in archivos],
        }
        datos.update(cambios)
        ruta = self.raiz / ".borradores" / "busqueda.json"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos), encoding="utf-8", newline="\n")
        return ruta

    def ecuacion_esperada(self, fuente: str) -> str:
        """La ecuación que el protocolo prescribe para `fuente` (la versión vigente actual)."""
        protocolo = decodificar_protocolo(leer_bytes_protocolo(self.protocolo)).protocolo
        conjunto = generar_ecuaciones(protocolo)
        generica = conjunto.ecuaciones[-1]
        ecuacion = next((e for e in conjunto.ecuaciones if e.fuente == fuente), generica)
        assert ecuacion.texto is not None
        return ecuacion.texto

    def registrar(
        self,
        busqueda: Path,
        *,
        respuestas: list[str | None] | None = None,
        registrado_por: str = "investigador-1",
        interactiva: bool = True,
        comprobador: Any = sin_comprobar_git,
    ) -> tuple[ResultadoRegistro, TerminalSimulada]:
        terminal = TerminalSimulada(
            respuestas
            if respuestas is not None
            else ["2026-10-14", "09:30", "", "registrar imp-0001"],
            interactiva=interactiva,
        )
        resultado = registrar_busqueda(
            busqueda,
            registrado_por,
            self.raiz,
            terminal,
            reloj=reloj_de_registro(),
            desfase_sistema=desfase_menos_cinco,
            comprobador=comprobador,
        )
        return resultado, terminal

    def archivos(self) -> list[str]:
        """Todos los archivos del estudio, relativos, para comprobar que no se escribió nada."""
        return sorted(
            p.relative_to(self.raiz).as_posix() for p in self.raiz.rglob("*") if p.is_file()
        )


def crear_estudio(
    base: Path,
    *,
    aprobar: bool = True,
    configuracion: str | None = CONFIGURACION_COMPLETA,
    fuentes_extra: str = "",
) -> Estudio:
    """Crea `base/estudio` con el protocolo sintético (aprobado) y la configuración."""
    raiz = base / "estudio"
    protocolo = raiz / "protocolo" / "protocolo.yaml"
    protocolo.parent.mkdir(parents=True)
    texto = RUTA_PROTOCOLO_SINTETICO.read_text(encoding="utf-8")
    assert FUENTE_SCOPUS in texto
    texto = texto.replace(FUENTE_SCOPUS, FUENTE_SCOPUS + fuentes_extra)
    protocolo.write_bytes(texto.encode("utf-8"))
    if aprobar:
        aprobar_protocolo(protocolo)
    if configuracion is not None:
        escribir(raiz / "publicacion_datos.yaml", configuracion)
    (base / "descargas").mkdir()
    return Estudio(raiz, protocolo, base / "descargas")


def copia_del_estudio(origen: Path, destino: Path) -> None:
    shutil.copytree(origen, destino)
