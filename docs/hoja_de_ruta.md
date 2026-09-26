# Hoja de ruta

Se avanza un hito a la vez. Un hito está terminado solo cuando:

- cumple su criterio de terminado;
- las pruebas pasan en CI (Windows y Ubuntu);
- la documentación está actualizada;
- sus decisiones relevantes tienen ADR.

Cada hito cerrado se etiqueta con una versión (`v0.N.0`).

## Pendientes del investigador

- [ ] Nombre completo y ORCID (para `LICENSE` y `CITATION.cff`).
- [ ] Usuario de GitHub y nombre del repositorio del caso piloto.
- [x] Tema, pregunta general, PCC y preguntas específicas del caso piloto (recibidos el 2026-09-25; ver `caso_piloto_local/contexto_caso_piloto.md`).
- [ ] Decisiones O1–O10 del caso piloto: se toman con el comando `/protocolo` en el hito 1.
- [ ] Criterios de inclusión y exclusión, y de 5 a 10 artículos clave conocidos por vías distintas de las APIs, para el conjunto de validación.
- [ ] Claves gratuitas de API (antes del hito 3): OpenAlex, Semantic Scholar, NCBI (opcional) y Springer Nature.

## Hito 0: Entorno y esqueleto (`v0.0.1`) · ✅ completo (2026-09-25)

1. Verificar que funcionen git, uv, gh y la configuración de git (`user.name`, `user.email`), sin instalar nada sin aprobación.
2. `git init` y primer commit con la documentación existente.
3. Crear el paquete con uv en estructura `src/` (`uv init --package`), con Python 3.12 fijado (`.python-version`) y metadatos en `pyproject.toml`.
4. Agregar como dependencias de desarrollo pytest, pytest-cov, ruff y mypy, configurados en `pyproject.toml` (mypy estricto).
5. CLI mínima: `agentresearch --version`, con su prueba.
6. `LICENSE` (MIT), `CITATION.cff` y `CHANGELOG.md`.
7. GitHub Actions: ruff, mypy y pytest en `windows-latest` y `ubuntu-latest`, con uv.
8. Crear el repositorio público en GitHub con `gh`, hacer el primer push y etiquetar.

**Criterio de terminado:** CI en verde en ambos sistemas, y `uv run agentresearch --version` funciona en Windows.

## Hito 1: Protocolo y trazabilidad (`v0.1.0`) · en curso: 1a ✅ y 1b ✅ (2026-09-26), sigue 1c

Especificación detallada, dividida en los sub-hitos 1a a 1e: [especificaciones/hito_1_protocolo_y_trazabilidad.md](especificaciones/hito_1_protocolo_y_trazabilidad.md).

- **Trazabilidad:** registro JSONL de solo adición, hashes, versión del agente y fecha y hora UTC.
- **Modelo del protocolo** con pydantic:
  - justificación, preguntas (`PI*`), PCC con equivalencia PICOC;
  - criterios (`CI*`, `CE*`) con la fase en que se aplican y ejemplos;
  - revisores, regla A–F y umbral de concordancia;
  - estrategias de identificación y criterio de parada;
  - facetas y formulario de extracción;
  - financiación.
- **Validaciones:** IDs únicos, cada pregunta vinculada a datos de extracción, cada criterio con su fase, y advertencias metodológicas (sección 2 de `reglas_metodologicas.md`).
- **Enmiendas** versionadas.
- **Ecuaciones de búsqueda** generadas desde los bloques PCC (OR dentro de cada bloque, AND entre bloques) en la sintaxis de cada fuente: OpenAlex, PubMed, Scopus y Web of Science.
- **Plantilla de estudio:** `CLAUDE.md` y el comando `/protocolo`, que entrevista al investigador y propone opciones.
- **Comandos:** `agentresearch nuevo-estudio` y `agentresearch protocolo validar`.

- **Insumo del caso piloto:** `/protocolo` parte de `caso_piloto_local/contexto_caso_piloto.md` y conduce las decisiones O1–O10.

**Criterio de terminado:** el protocolo del caso piloto se construye con el comando guiado, se valida y queda versionado en su repositorio.

## Hito 2: Registros e importación (`v0.2.0`)

- Modelo normalizado de registro con procedencia y distinción entre artículo y estudio.
- Lectores de RIS, BibTeX, CSV de Scopus, WoS (.txt) y CSV genérico, probados con archivos sintéticos.
- Hash de cada archivo importado y conteos por fuente para el diagrama de flujo.

**Criterio de terminado:** se importan exportaciones reales del caso piloto (sin versionar las que tengan restricciones) con conteos correctos.

## Hito 3: Conectores de APIs (`v0.3.0`)

- Interfaz común, caché de respuestas crudas, control de tasa y claves en `.env` (con `.env.ejemplo` versionado).
- Conectores de OpenAlex, PubMed, Semantic Scholar, Springer Nature OA, Crossref y AGROVOC.
- Volver a verificar límites y términos de cada API y registrarlos en ADR-0003.

**Criterio de terminado:** búsqueda del caso piloto en las APIs, con respuestas crudas guardadas y pruebas simuladas.

## Hito 4: Deduplicación (`v0.4.0`)

- Coincidencia por DOI normalizado, y por título difuso más año, con umbral configurable.
- Grupos de duplicados con la regla aplicada; los casos dudosos pasan a revisión humana.

**Criterio de terminado:** conteos de duplicados listos para el diagrama de flujo, con muestra verificada manualmente.

## Hito 5: Cribado por título y resumen (`v0.5.0`)

- Prefiltros deterministas: año, idioma y tipo de documento.
- Prompt versionado de cribado; comandos `preparar-lote`, `registrar` y `estado`, con verificación de la evidencia literal.
- Hoja Excel ciega: exportar e importar.
- Reglas A–F, kappa de Cohen, porcentaje de acuerdo y matriz de confusión.
- Flujo del piloto: aplicación en voz alta, piloto, ajuste de criterios y umbral; luego conciliación.
- Medición de estabilidad del LLM sobre una muestra.

**Criterio de terminado:** piloto de cribado del caso real con concordancia reportada.

## Hito 6: Conjunto de validación y bola de nieve (`v0.6.0`)

- Sensibilidad de la búsqueda frente al conjunto de validación.
- Bola de nieve según Wohlin (2014) con OpenAlex y Semantic Scholar: iteraciones, origen de cada candidato e inclusión definitiva antes de continuar.
- Criterio de parada.

## Hito 7: Texto completo (`v0.7.0`)

- Vínculo entre PDF y registro por hash, extracción de texto con pypdf, y cribado de texto completo con motivos de exclusión.

## Hito 8: Extracción y clasificación (`v0.8.0`)

- Formulario de extracción ligado a las preguntas.
- *Keywording* y *card sorting* para el esquema emergente; facetas con definiciones y ejemplos.
- Segundo revisor con concordancia; evaluación de calidad opcional.

## Hito 9: Análisis y visualización (`v0.9.0`)

- Conteos por faceta, series temporales, mapas de burbujas y de calor, generados desde los datos.

## Hito 10: Reporte (`v1.0.0`)

- Diagrama de flujo PRISMA-ScR, checklist con la ubicación de cada ítem, tabla completa de estudios con su clasificación, declaración de uso de IA, amenazas a la validez y desviaciones del protocolo.
- Paquete del estudio listo para Zenodo.

**Criterio de terminado:** el reporte del caso piloto se regenera de forma idéntica desde los datos (prueba de reproducibilidad).

## Notas de revisión para hitos futuros

Hallazgos de las revisiones del asesor y de auditorías, pendientes para el hito indicado. Se tachan o eliminan cuando se resuelven.

- **1c:** implementar el anclaje del registro encadenado (número de eventos y hash del último) en `protocolo historial` y en los reportes, según el punto 10 del ADR-0006. Sin anclaje no se detecta la eliminación de eventos finales.
- **1c:** agregar la advertencia P-A09, "piloto de cribado sin tamaño definido" (`seleccion.piloto.tamano` igual a 0). El proceso de selección exige un piloto con medición de concordancia antes del cribado completo (Ali y Petersen, 2014; Petersen et al., 2015, figura 17). La plantilla trae 0 por defecto, y hoy eso pasa sin aviso.
- **1e:** mitigar el límite conocido de ruamel.yaml documentado en el ADR-0006: al eliminar el último elemento antes del comentario de una sección, ese comentario se pierde. Como `/protocolo` escribirá sección por sección, la escritura debe restaurar los comentarios de sección de primer nivel tomándolos de la plantilla, que es su fuente canónica, y probarlo vaciando una lista.
- **1e:** la plantilla del repositorio de estudio debe incluir un `.gitattributes` con `* text=auto eol=lf`. Git para Windows convierte los fines de línea por defecto, y eso alteraría los hashes de archivos como el protocolo.
- **1e:** decidir O1 (opción A o C) del caso piloto con `/protocolo`.
- **Cierre del hito 1:** evaluar fijar los sistemas de la integración continua (p. ej. `ubuntu-24.04`) en vez de `*-latest`, para que el entorno de pruebas no cambie sin decisión explícita. GitHub anunció la migración de `ubuntu-latest` a Ubuntu 26 desde el 19 de octubre de 2026.
- **Hito 5:** agregar escritura por lotes al registro encadenado, verificando la cadena una vez por lote. Con miles de decisiones, verificar el archivo completo en cada evento crece de forma cuadrática.
- **Hito 5:** elegir el modelo del cribado con datos. En el piloto se compara la concordancia con el investigador de al menos dos configuraciones (p. ej. Sonnet 5 en esfuerzo alto y Opus 5.5 en medio), y se fija el identificador completo del modelo para todo el estudio. Cambiarlo después es una enmienda del protocolo.
- **Proceso:** toda afirmación sobre versiones, sintaxis o límites de APIs y herramientas se verifica contra la fuente oficial o la integración continua. Por ejemplo, `astral-sh/setup-uv@v10` no existía, y la integración continua lo detectó.
- **Proceso:** GitHub Copilot se usa solo como auditor de lectura; únicamente Claude Code edita el código.
