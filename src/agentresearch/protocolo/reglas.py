"""Catálogo de reglas de validación del protocolo, con ID estable y referencia.

Los ID son estables: aparecen en los mensajes, en la salida JSON y en las
pruebas, y nunca se reutilizan para otra regla. Una regla que deje de
aplicarse se retira del catálogo, pero su ID no se asigna a otra.

- Los errores (P-E) impiden aprobar el protocolo.
- Las advertencias (P-A) no lo impiden, pero el investigador debe revisarlas.
"""

from dataclasses import dataclass
from typing import Literal

Severidad = Literal["error", "advertencia"]


@dataclass(frozen=True, slots=True)
class Regla:
    """Una regla de validación del protocolo."""

    id: str
    severidad: Severidad
    descripcion: str
    referencia: str


_CATALOGO = (
    Regla(
        "P-E00",
        "error",
        "El archivo es legible, es YAML válido y cumple el esquema del protocolo",
        "Esquema del protocolo, versión 1 (ADR-0006)",
    ),
    Regla(
        "P-E01",
        "error",
        "IDs únicos y con el patrón de su tipo: PI, CI, CE, DE, F y B seguidos de un número",
        "CLAUDE.md, regla 2 (toda decisión cita el ID del criterio)",
    ),
    Regla(
        "P-E02",
        "error",
        "Toda referencia (responde_con, derivada_de, preguntas, cruces) apunta a un ID existente",
        "Reglas metodológicas del agente, §2 (contenido mínimo del protocolo)",
    ),
    Regla(
        "P-E03",
        "error",
        "Cada pregunta descriptiva tiene al menos un dato que la responde; "
        "cada pregunta analítica declara de qué cruces se deriva",
        "Petersen et al. (2015), tabla 3",
    ),
    Regla(
        "P-E04",
        "error",
        "Población y concepto no están vacíos; hay al menos un bloque de búsqueda "
        "y cada bloque tiene al menos un término",
        "PRISMA-ScR, ítems 4 y 8; Peters et al. (2024), JBI",
    ),
    Regla(
        "P-E05",
        "error",
        "Cada criterio declara su fase",
        "PRISMA-ScR, ítem 6",
    ),
    Regla(
        "P-E06",
        "error",
        "regla_combinacion.avanzan contiene A y no contiene F",
        "Petersen et al. (2015), tabla 6",
    ),
    Regla(
        "P-E07",
        "error",
        "Hay al menos un revisor humano",
        "CLAUDE.md, regla 1; declaración conjunta Cochrane, Campbell, JBI y CEE (2025)",
    ),
    Regla(
        "P-E08",
        "error",
        "umbral_kappa está entre 0 y 1; el tamaño del lote es un entero positivo",
        "Landis y Koch (1977)",
    ),
    Regla(
        "P-A01",
        "advertencia",
        "Criterio que exige evaluación empírica",
        "Petersen et al. (2015), §5.1.2",
    ),
    Regla(
        "P-A02",
        "advertencia",
        "Contexto marcado como restrictivo, o usado como bloque AND de búsqueda",
        "Petersen et al. (2015), §5.1.2",
    ),
    Regla(
        "P-A03",
        "advertencia",
        "Solo una estrategia de identificación activa",
        "Petersen et al. (2015), tabla 10",
    ),
    Regla(
        "P-A04",
        "advertencia",
        "Conjunto de validación inactivo o con menos de 5 artículos",
        "Petersen et al. (2015), §5.1.2",
    ),
    Regla(
        "P-A05",
        "advertencia",
        "Periodo o idioma restringido sin justificación",
        "PRISMA-ScR, ítem 6",
    ),
    Regla(
        "P-A06",
        "advertencia",
        "Categoría de faceta sin definición, regla o ejemplos",
        "Wohlin et al. (2013)",
    ),
    Regla(
        "P-A07",
        "advertencia",
        "Acrónimo corto (4 letras o menos, en mayúsculas) suelto en un bloque, "
        "con riesgo de colisión",
        "Lección del ejercicio previo del caso piloto",
    ),
    Regla(
        "P-A08",
        "advertencia",
        "Sin un segundo revisor humano para el piloto de cribado",
        "Petersen et al. (2015), §5.1.2",
    ),
    Regla(
        "P-A09",
        "advertencia",
        "Piloto de cribado sin tamaño definido",
        "Ali y Petersen (2014); Petersen et al. (2015), figura 17",
    ),
)

REGLAS: dict[str, Regla] = {regla.id: regla for regla in _CATALOGO}
"""Reglas por ID, en orden: primero los errores y luego las advertencias."""
