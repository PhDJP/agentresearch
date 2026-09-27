# Agentresearch: contexto para Claude Code

Claude Code lee este archivo al iniciar cada sesión. Es corto a propósito: cada línea consume cuota del plan Pro en todas las sesiones. Los detalles están en `docs/` y se leen solo cuando la tarea los necesita.

## Qué es este proyecto

Agentresearch es un agente investigador que guía y gestiona, paso a paso, un estudio de mapeo sistemático de la literatura. Combina tres referentes:

- Kitchenham: proceso y protocolo (planificación, ejecución, reporte).
- Petersen et al. (2008, 2015): clasificación, *keywording*, reglas de decisión, mapas.
- PRISMA-ScR (Tricco et al., 2018): reporte, con checklist de 22 ítems y diagrama de flujo.

Es para uso académico doctoral. Calidad de software, rigor científico, explicabilidad y reproducibilidad son requisitos, no deseables.

Caso piloto: mapeo sistemático de los subproductos de la producción de cannabidiol (CBD): métodos de obtención, propiedades caracterizadas y aplicaciones (ciencias agrarias y agroindustriales). El contexto, la propuesta v0 y las decisiones pendientes están en `caso_piloto_local/contexto_caso_piloto.md`, carpeta no versionada porque es una propuesta doctoral inédita.

## Arquitectura

Claude Code (plan Pro, sin API de Anthropic) es el cerebro conversacional; el paquete Python `agentresearch` es el motor determinista. Detalle en `docs/arquitectura.md`.

- El paquete hace todo lo que no requiere juicio: conectores de APIs, importación, deduplicación, registro de decisiones, conteos PRISMA, gráficos y reportes.
- Claude Code conversa con el investigador, propone opciones y emite juicios (cribado, clasificación) siempre a través de comandos del paquete, que validan y registran cada salida.
- No se usa la API de Anthropic ni ningún LLM de pago o local. No agregar dependencias que lo requieran.

## Reglas metodológicas no negociables

1. El LLM propone; el investigador decide. Toda decisión registra quién la tomó (humano, o LLM con el identificador exacto del modelo).
2. Toda decisión de cribado o clasificación cita el ID del criterio del protocolo (p. ej. `CI2`, `CE3`) y un fragmento literal del registro como evidencia.
3. Revisión independiente y ciega: el lote que ve el LLM no contiene decisiones humanas, y la hoja del humano no contiene decisiones del LLM, hasta la conciliación.
4. Las decisiones de varios revisores se combinan con las reglas A–F de Petersen et al. (2015); la regla se configura en el protocolo.
5. El protocolo está versionado. Todo cambio después de iniciar la búsqueda es una enmienda con fecha y justificación.
6. Nunca inventar referencias, DOIs, cifras ni datos. Todo registro procede de una fuente con su respuesta cruda o exportación guardada y su hash.
7. Artículo no es lo mismo que estudio (Kitchenham et al., 2011): el modelo de datos distingue ambos.
8. El resultado publica todos los estudios incluidos con su clasificación individual.
9. Si el investigador no tiene un dato del protocolo, el agente genera de 2 a 4 opciones fundamentadas (pros, contras y referencia metodológica). El investigador elige, y la elección y las alternativas quedan registradas.

Tablas y detalle: `docs/metodologia/reglas_metodologicas.md`.

## Convenciones de código

- Python 3.12 con `uv` y `uv.lock` versionado. Nunca `pip install` suelto ni el Python de Anaconda.
- Todo en español: código, docstrings, mensajes, documentación y reportes. Identificadores sin tildes ni ñ (`criterio_exclusion`, `anio`); el texto visible lleva ortografía completa.
- Estructura `src/agentresearch/`. Archivos de texto en UTF-8 con fin de línea LF.
- Tipado estricto con mypy, estilo con ruff, pruebas con pytest. Ningún cambio está terminado sin pruebas que pasen.
- Esquemas de datos con pydantic. Los datos de un estudio se guardan en texto versionable (YAML, JSONL, CSV), no en bases de datos binarias.
- Las pruebas no usan red: las llamadas a APIs se simulan; las pruebas en vivo van marcadas aparte.
- Solo dependencias con licencia permisiva compatible con MIT (nada AGPL/GPL; por ejemplo, no PyMuPDF). Cada dependencia nueva se justifica en el commit o en un ADR.
- Las claves de API viven solo en `.env`, que nunca se versiona ni se muestra en el chat.

## Forma de trabajo

- Antes de un cambio grande, proponer un plan y esperar aprobación.
- Commits pequeños, con mensajes en español (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
- Toda decisión de diseño relevante se registra como ADR en `docs/decisiones/`.
- Avanzar hito por hito según `docs/hoja_de_ruta.md`, sin adelantar hitos.
- Este repositorio es la herramienta. Los datos de cada estudio van en un repositorio aparte.
- `referencias_locales/` tiene PDFs con derechos de autor: se pueden leer para verificar, pero nunca se versionan ni se copian textualmente.
- `caso_piloto_local/` es privado: no se versiona ni se copia a archivos versionados. Las pruebas usan datos sintéticos, no los del caso piloto.
- Un asesor en otra sesión (Claude en Cowork) revisa y escribe documentos de diseño en `docs/`. Solo Claude Code edita el código.

## Estado actual

Hito 0 completo (`v0.0.1`, repositorio público https://github.com/PhDJP/agentresearch). Hito 1 en curso: 1a, 1b y 1c completos (ADR-0006 y ADR-0008). El 1d (ecuaciones, ADR-0009 en propuesta) está en revisión en la rama `hito-1d` (PR #2). Luego sigue el 1e: ver `docs/especificaciones/hito_1_protocolo_y_trazabilidad.md`.
