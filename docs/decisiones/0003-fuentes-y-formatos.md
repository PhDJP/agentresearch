# ADR-0003: Fuentes de información y formatos de importación

- Estado: Aceptada
- Fecha: 2026-09-25
- Participantes: investigador doctoral y Claude (asesor)

## Contexto

El agente debe usar recursos gratuitos, y el investigador tiene acceso institucional a bases de suscripción (Scopus, ScienceDirect, Web of Science, IEEE, etc.) solo por su interfaz web. El caso piloto es del área agraria y agroindustrial. Las condiciones de acceso de cada API se verificaron el 2026-09-25; deben volver a verificarse al implementar cada conector.

## Decisión

### APIs en la versión 1

| Fuente | Uso | Acceso (verificado 2026-09-25) |
|--------|-----|--------------------------------|
| OpenAlex | Búsqueda multidisciplinaria, citas para bola de nieve | Clave gratuita obligatoria; 1 USD de uso diario gratis (unas 1.000 búsquedas o 10.000 consultas con filtro al día); datos CC0 |
| Semantic Scholar | Búsqueda, referencias y citas para bola de nieve | Clave gratuita; 1 solicitud por segundo garantizada |
| PubMed (NCBI E-utilities) | Literatura biomédica y de salud | Gratuito; clave opcional que aumenta el límite (confirmar límites al implementar) |
| Springer Nature Open Access API | Metadatos y texto de artículos de acceso abierto | Clave gratuita (confirmar cuotas al implementar) |
| Crossref | Completar metadatos por DOI y apoyar la deduplicación | Gratuito, sin clave |
| AGROVOC (FAO) | Tesauro agrícola multilingüe para proponer sinónimos en la ecuación PCC | Gratuito; SPARQL y API REST (Skosmos) |

### Importación de exportaciones manuales

RIS, BibTeX, CSV de Scopus, Web of Science en formato de etiquetas (.txt) y CSV genérico con mapeo de columnas configurable, que cubre, por ejemplo, las exportaciones de Lens.

### Texto completo

El cribado se hace por título y resumen. En la fase de texto completo, el agente trabaja con los PDF que el investigador descarga con su acceso institucional. En la versión 1 no se descargan automáticamente versiones de acceso abierto.

### Reglas para todas las fuentes

- Cada búsqueda guarda la consulta exacta, la fuente, la fecha y hora, los parámetros, la respuesta cruda y el número de resultados.
- Cada archivo importado guarda su hash SHA-256.
- Las claves de API viven en `.env` y nunca se versionan.

## Alternativas consideradas

- **API de Elsevier (Scopus y ScienceDirect):** se deja para una fase posterior como conector opcional, porque depende de la red institucional y de sus términos.
- **AGRIS (FAO) y Lens:** no se encontró una API pública de AGRIS, y la API de Lens solo ofrece una prueba de 14 días. Se usan mediante exportación manual.
- **CORE y Europe PMC:** no se incluyen en la versión 1; pueden añadirse después.

## Consecuencias

- Los conectores comparten una interfaz común, una caché de respuestas crudas y un control de tasa, de modo que agregar una fuente nueva no altera el resto.
- Como las fuentes cambian con el tiempo, la búsqueda es reproducible a partir de las respuestas crudas guardadas, no volviendo a consultar la API.
