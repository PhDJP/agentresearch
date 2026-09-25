# ADR-0004: Trazabilidad de decisiones y reproducibilidad

- Estado: Aceptada
- Fecha: 2026-09-25
- Participantes: investigador doctoral y Claude (asesor)

## Contexto

Un LLM puede dar respuestas distintas ante la misma entrada, y en Claude Code no se controla la temperatura. PRISMA-ScR asegura la transparencia del reporte, pero no la reproducibilidad de los juicios del modelo. La declaración conjunta sobre IA en síntesis de evidencia (Cochrane, Campbell, JBI y CEE, 2025) exige además que los investigadores sigan siendo responsables de cada uso de IA y puedan justificarlo.

## Decisión

Distinguimos dos propiedades y declaramos cuál garantizamos:

- **Reproducible (se garantiza):** a partir de los artefactos registrados en el repositorio del estudio, volver a ejecutar el pipeline produce exactamente los mismos conteos, tablas, gráficos y reportes.
- **Regenerable (no se garantiza; se mide):** volver a consultar al LLM puede producir decisiones distintas. Esta variabilidad se estima repitiendo el cribado sobre una muestra y reportando la concordancia.

Para lograrlo:

1. **Registro de decisiones.** Es un archivo JSONL al que solo se añaden líneas. Cada decisión guarda:
   - el registro evaluado y la fase;
   - el revisor (humano, o LLM con el identificador exacto del modelo);
   - la decisión (incluir, dudoso o excluir);
   - los IDs de los criterios aplicados;
   - un fragmento literal del registro como evidencia, más una justificación breve;
   - el lote, la versión del protocolo, el hash del prompt y la versión del agente;
   - la fecha y hora en UTC.
2. **Verificación de la evidencia.** El paquete rechaza cualquier decisión cuya evidencia no aparezca literalmente en el título, el resumen o las palabras clave del registro. Es una salvaguarda contra respuestas inventadas.
3. **Prompts versionados.** Los prompts de cada tarea son archivos del paquete, y cada decisión registra su hash.
4. **Protocolo versionado.** Las enmiendas llevan fecha y justificación, y se reportan como desviaciones.
5. **Entorno fijado.** `uv.lock` fija las dependencias, y el repositorio del estudio fija la versión exacta del agente (etiqueta o commit).
6. **Revisión ciega.** El lote del LLM no incluye decisiones humanas, y la hoja Excel del humano no incluye decisiones del LLM. Al reimportar la hoja se guarda su hash.
7. **Concordancia.** Se reporta la kappa de Cohen entre revisores, con porcentaje de acuerdo y matriz de confusión, tanto en el piloto como en el cribado completo.
8. **Evidencia pública.** Todo lo anterior se versiona en el repositorio del estudio en GitHub y se archiva en Zenodo con DOI al publicar.

## Alternativas consideradas

- **Confiar solo en el reporte PRISMA:** insuficiente, porque no permite auditar decisión por decisión.
- **Usar temperatura 0 mediante la API:** no está disponible sin API, y aun con temperatura 0 no hay determinismo garantizado.

## Consecuencias

- Cada comando que registra decisiones debe validar el esquema antes de escribir. Las pruebas cubren los casos de rechazo.
- El artículo podrá declarar con precisión qué hizo el LLM, con qué modelo, con qué prompts y con qué concordancia frente al investigador.
