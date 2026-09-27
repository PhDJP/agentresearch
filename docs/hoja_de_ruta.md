# Hoja de ruta

Se avanza un hito a la vez. Un hito está terminado solo cuando:

- cumple su criterio de terminado;
- las pruebas pasan en CI (Windows y Ubuntu);
- la documentación está actualizada;
- sus decisiones relevantes tienen ADR.

Cada hito cerrado se etiqueta con una versión (`v0.N.0`).

## Estrategia de validación (decisión del 2026-09-27)

Primero se termina el agente y después se usa en el caso piloto. Por eso:

- **Cada hito se acepta con un estudio de demostración:** un tema real y neutral, distinto del caso piloto, de pocos registros, que recorre el flujo completo hasta ese hito. El tema y la ubicación de sus datos se deciden en el sub-hito 1e (ADR-0007). Los datos del estudio de demostración nunca son los del caso piloto.
- **Los formatos reales se prueban sin hacer el mapeo:** en el hito 2 se importan exportaciones reales de una búsqueda de prueba (pocos registros), solo para verificar los lectores. No es la búsqueda oficial de ningún estudio.
- **El caso piloto se ejecuta en el hito 11 (aceptación),** con el agente terminado. Así, el protocolo de la tesis se construye una sola vez con la herramienta completa, y las mejoras del agente durante el desarrollo no generan enmiendas en él.
- **La versión `v1.0.0` se reserva para el agente validado con el caso piloto real.** El hito 10 cierra como `v0.10.0`.

Riesgo aceptado: los problemas que solo aparecen con datos reales se descubren al final. Se mitiga con un estudio de demostración realista y con las exportaciones reales de prueba del hito 2; lo que aparezca en el hito 11 se corrige con versiones de parche (`v1.0.x`).

## Pendientes del investigador

- [ ] Nombre completo y ORCID (para `LICENSE` y `CITATION.cff`).
- [ ] Nombre del repositorio privado del caso piloto (antes del hito 11; propuesta: `mapeo-subproductos-cbd`).
- [x] Tema, pregunta general, PCC y preguntas específicas del caso piloto (recibidos el 2026-09-25; ver `caso_piloto_local/contexto_caso_piloto.md`).
- [ ] Decisiones O1–O10 del caso piloto: se toman con el comando `/protocolo` en el hito 11.
- [ ] Criterios de inclusión y exclusión, y de 5 a 10 artículos clave conocidos por vías distintas de las APIs, para el conjunto de validación (hito 11).
- [ ] Claves gratuitas de API (antes del hito 3): OpenAlex ✅ (2026-09-27), Semantic Scholar, NCBI (opcional) y Springer Nature.

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

## Hito 1: Protocolo y trazabilidad (`v0.1.0`) · en curso: 1a ✅, 1b ✅ y 1c ✅ (2026-09-26) y 1d ✅ (2026-09-27), sigue 1e

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

- **Estudio de demostración:** `/protocolo` se prueba de punta a punta con un estudio de demostración (ver «Estrategia de validación»). El caso piloto se construye en el hito 11.

**Criterio de terminado:** el protocolo del estudio de demostración se construye con el comando guiado, se valida, se aprueba en la terminal del investigador y queda versionado en su repositorio con su historial.

## Hito 2: Registros e importación (`v0.2.0`)

- Modelo normalizado de registro con procedencia y distinción entre artículo y estudio.
- Lectores de RIS, BibTeX, CSV de Scopus, WoS (.txt) y CSV genérico, probados con archivos sintéticos.
- Hash de cada archivo importado y conteos por fuente para el diagrama de flujo.

**Criterio de terminado:** se importan exportaciones reales de una búsqueda de prueba en cada formato (pocos registros; sin versionar las que tengan restricciones) con conteos correctos, y el estudio de demostración importa las suyas.

## Hito 3: Conectores de APIs (`v0.3.0`)

- Interfaz común, caché de respuestas crudas, control de tasa y claves en `.env` (con `.env.ejemplo` versionado).
- Conectores de OpenAlex, PubMed, Semantic Scholar, Springer Nature OA, Crossref y AGROVOC.
- Volver a verificar límites y términos de cada API y registrarlos en ADR-0003.

**Criterio de terminado:** búsqueda del estudio de demostración en las APIs, con respuestas crudas guardadas (sin credenciales) y pruebas simuladas.

## Hito 4: Deduplicación (`v0.4.0`)

- Coincidencia por DOI normalizado, y por título difuso más año, con umbral configurable.
- Grupos de duplicados con la regla aplicada; los casos dudosos pasan a revisión humana.

**Criterio de terminado:** conteos de duplicados del estudio de demostración listos para el diagrama de flujo, con muestra verificada manualmente.

## Hito 5: Cribado por título y resumen (`v0.5.0`)

- Prefiltros deterministas: año, idioma y tipo de documento.
- Prompt versionado de cribado; comandos `preparar-lote`, `registrar` y `estado`, con verificación de la evidencia literal.
- Hoja Excel ciega: exportar e importar.
- Reglas A–F, kappa de Cohen, porcentaje de acuerdo y matriz de confusión.
- Flujo del piloto: aplicación en voz alta, piloto, ajuste de criterios y umbral; luego conciliación.
- Medición de estabilidad del LLM sobre una muestra.

**Criterio de terminado:** piloto de cribado del estudio de demostración, de punta a punta (lote del LLM, hoja ciega del investigador, conciliación), con concordancia reportada. La concordancia sobre el tema real se mide en el hito 11.

## Hito 6: Conjunto de validación y bola de nieve (`v0.6.0`)

- Sensibilidad de la búsqueda frente al conjunto de validación.
- Bola de nieve según Wohlin (2014) con OpenAlex y Semantic Scholar: iteraciones, origen de cada candidato e inclusión definitiva antes de continuar.
- Criterio de parada.

**Criterio de terminado:** el estudio de demostración reporta la sensibilidad frente a su conjunto de validación y completa al menos una iteración de bola de nieve con el origen de cada candidato.

## Hito 7: Texto completo (`v0.7.0`)

- Vínculo entre PDF y registro por hash, extracción de texto con pypdf, y cribado de texto completo con motivos de exclusión.

**Criterio de terminado:** el estudio de demostración completa el cribado de texto completo con los motivos de exclusión registrados.

## Hito 8: Extracción y clasificación (`v0.8.0`)

- Formulario de extracción ligado a las preguntas.
- *Keywording* y *card sorting* para el esquema emergente; facetas con definiciones y ejemplos.
- Segundo revisor con concordancia; evaluación de calidad opcional.

**Criterio de terminado:** el estudio de demostración completa la extracción y la clasificación con concordancia reportada.

## Hito 9: Análisis y visualización (`v0.9.0`)

- Conteos por faceta, series temporales, mapas de burbujas y de calor, generados desde los datos.

**Criterio de terminado:** los gráficos del estudio de demostración se generan desde sus datos.

## Hito 10: Reporte (`v0.10.0`)

- Diagrama de flujo PRISMA-ScR, checklist con la ubicación de cada ítem, tabla completa de estudios con su clasificación, declaración de uso de IA, amenazas a la validez y desviaciones del protocolo.
- Paquete del estudio listo para Zenodo.

**Criterio de terminado:** el reporte del estudio de demostración se regenera de forma idéntica desde sus datos (prueba de reproducibilidad).

## Hito 11: Aceptación con el caso piloto (`v1.0.0`)

- Crear el repositorio privado del caso piloto con `nuevo-estudio` y el insumo `caso_piloto_local/contexto_caso_piloto.md`.
- Construir el protocolo con `/protocolo`: decisiones O1–O10, criterios, conjunto de validación y variantes de los términos truncados; aprobarlo como `1.0.0`.
- Elegir el modelo del cribado con datos (ver la nota del hito 5) y fijar su identificador completo.
- Ejecutar el mapeo completo: búsquedas, importación, deduplicación, cribado, bola de nieve, texto completo, extracción, análisis y reporte.
- Corregir con versiones de parche lo que el caso real revele.

**Criterio de terminado:** el reporte del caso piloto se regenera de forma idéntica desde sus datos, y el agente queda etiquetado como `v1.0.0`.

## Notas de revisión para hitos futuros

Hallazgos de las revisiones del asesor y de auditorías, pendientes para el hito indicado. Se tachan o eliminan cuando se resuelven.

- ~~**1c:** implementar el anclaje del registro encadenado (número de eventos y hash del último) en `protocolo historial` y en los reportes, según el punto 10 del ADR-0006. Sin anclaje no se detecta la eliminación de eventos finales.~~ Resuelto en 1c (ADR-0008, puntos 19 a 21).
- ~~**1c:** agregar la advertencia P-A09, "piloto de cribado sin tamaño definido" (`seleccion.piloto.tamano` igual a 0). El proceso de selección exige un piloto con medición de concordancia antes del cribado completo (Ali y Petersen, 2014; Petersen et al., 2015, figura 17). La plantilla trae 0 por defecto, y hoy eso pasa sin aviso.~~ Resuelto en 1c (ADR-0008, punto 25).
- ~~**1e:** `nuevo-estudio` debe crear `protocolo/eventos.jsonl` con su evento inicial y el `anclaje.json` correspondiente. `/protocolo` debe pedir al investigador que ejecute `aprobar`, `enmendar` y `decision confirmar` en su propia terminal. Valorar negar esos comandos en los permisos de Claude Code del estudio (ADR-0008, consecuencias).~~ Resuelto en 1e (ADR-0007, puntos 9, 12, 15 a 17).
- **1e:** verificar en la terminal real del investigador (PowerShell y la terminal de VS Code) que la confirmación interactiva funciona, y que Git Bash abierto como aplicación independiente (mintty) se rechaza con el mensaje que recomienda PowerShell o la terminal de VS Code. Las pruebas simulan la consola; en esta sesión solo se comprobó que las herramientas de Claude Code no la ofrecen.
- ~~**1e:** mitigar el límite conocido de ruamel.yaml documentado en el ADR-0006: al eliminar el último elemento antes del comentario de una sección, ese comentario se pierde. Como `/protocolo` escribirá sección por sección, la escritura debe restaurar los comentarios de sección de primer nivel tomándolos de la plantilla, que es su fuente canónica, y probarlo vaciando una lista.~~ Resuelto en 1e (ADR-0007, punto 14): se restauran los comentarios del propio archivo, que en un estudio nace de la plantilla.
- ~~**1e:** la plantilla del repositorio de estudio debe incluir un `.gitattributes` con `* text=auto eol=lf`. Git para Windows convierte los fines de línea por defecto, y eso alteraría los hashes de archivos como el protocolo.~~ Resuelto en 1e (ADR-0007, punto 4).
- **Hito 11:** decidir O1 (opción A o C) del caso piloto con `/protocolo`.
- **Antes del hito 11:** agregar un comando para registrar una actualización deliberada de las instrucciones del agente (`CLAUDE.md`, `.claude/settings.json` y las *skills*) con sus nuevos hashes, como evento del registro, y que la nota «instrucciones del agente modificadas» compare con el último registro. Hasta entonces, `validar` e `historial` muestran la nota desde el primer cambio, y el cambio se deshace con Git o se declara en el reporte (ADR-0007, punto 10).
- **Cierre del hito 1:** en POSIX, sincronizar el directorio (`os.open` del directorio y `os.fsync`) después de cada `os.replace` de la escritura atómica, para que el cambio de nombre también sobreviva a un corte de energía. El ADR-0008 (punto 14) lo omitió porque Windows no lo admite; en Windows se sigue omitiendo.
- **Cierre del hito 1:** evaluar fijar los sistemas de la integración continua (p. ej. `ubuntu-24.04`) en vez de `*-latest`, para que el entorno de pruebas no cambie sin decisión explícita. GitHub anunció la migración de `ubuntu-latest` a Ubuntu 26 desde el 19 de octubre de 2026.
- **Hito 2:** al importar una exportación de una búsqueda manual (Scopus, Web of Science u otra base sin API), registrar además del hash y los conteos: la ecuación usada (versión y hash del protocolo de `ecuaciones.md`), la fecha y hora en que el investigador ejecutó la búsqueda, y el número de resultados que mostró la interfaz, para compararlo con los registros importados. PRISMA-ScR, ítem 7, exige reportar la fecha de cada búsqueda.
- **Hito 3:** los conectores de OpenAlex y PubMed aplican como parámetros los límites de la búsqueda (periodo, idiomas y tipos de documento), que `ecuaciones.md` solo lista como texto para esas fuentes (ADR-0009, punto 10).
- **Hito 3:** los conectores deben quitar `api_key` (y cualquier otra clave o credencial) de la URL, los parámetros y los encabezados que se guardan con la respuesta cruda y su hash, y de los mensajes de error y los registros. Una prueba debe verificar que la clave no aparece en nada de lo que se guarda.
- **Hito 3:** decidir si Semantic Scholar necesita un traductor propio de ecuaciones. Es fuente de búsqueda en el ADR-0003, pero el 1d solo traduce para OpenAlex, PubMed, Scopus, Web of Science y la versión genérica.
- **Hito 5:** agregar escritura por lotes al registro encadenado, verificando la cadena una vez por lote. Con miles de decisiones, verificar el archivo completo en cada evento crece de forma cuadrática.
- **Hito 5 (mecanismo) e hito 11 (elección):** elegir el modelo del cribado con datos. El hito 5 construye la comparación; en el piloto de cribado del caso real (hito 11) se compara la concordancia con el investigador de al menos dos configuraciones (p. ej. Sonnet 5 en esfuerzo alto y Opus 5.5 en medio), y se fija el identificador completo del modelo para todo el estudio. Cambiarlo después es una enmienda del protocolo.
- **Proceso:** toda afirmación sobre versiones, sintaxis o límites de APIs y herramientas se verifica contra la fuente oficial o la integración continua. Por ejemplo, `astral-sh/setup-uv@v10` no existía, y la integración continua lo detectó.
- **Proceso:** GitHub Copilot se usa solo como auditor de lectura; únicamente Claude Code edita el código.
