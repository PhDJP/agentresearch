# ADR-0001: Claude Code como cerebro y paquete Python como motor, sin API de pago

- Estado: Aceptada
- Fecha: 2026-09-25
- Participantes: investigador doctoral (autor del proyecto) y Claude (asesor, sesión Cowork)

## Contexto

- El investigador no cuenta con presupuesto para la API de Anthropic ni para otras APIs de modelos de lenguaje.
- Dispone de una suscripción a Claude Code (plan Pro), que tiene límites de uso por ventanas de 5 horas y semanales, compartidos con claude.ai y Cowork.
- Su computador no tiene GPU dedicada y tiene menos de 16 GB de RAM, así que los modelos locales (p. ej. con Ollama) no son prácticos.
- Muchos otros investigadores comparten estas restricciones, y el agente debe servirles también.
- El investigador eligió interactuar con el agente solo por chat en Claude Code, sin una aplicación web.

## Decisión

1. **Claude Code es el cerebro conversacional.** Guía al investigador por cada fase, pregunta, propone opciones cuando falta información y emite juicios de cribado y clasificación.
2. **El paquete Python `agentresearch` es el motor determinista.** Se encarga de:
   - conectores de APIs e importación de archivos;
   - deduplicación;
   - registro de decisiones y validación;
   - conteos, gráficos y reportes.

   Se usa mediante una interfaz de línea de comandos.
3. **Toda salida del LLM entra al sistema por comandos del paquete.** Estos comandos validan esquema, IDs y evidencia, y registran la procedencia. El LLM nunca escribe directamente en los archivos de datos del estudio.
4. **El comportamiento del agente en un estudio real se define en plantillas del paquete.** Son el `CLAUDE.md` del estudio y los comandos o *skills* de Claude Code, y se instalan en el repositorio de cada estudio.
5. **La revisión humana independiente se hace en hojas Excel.** El paquete las genera y las reimporta, sin construir una aplicación web.

## Alternativas consideradas

- **API de Anthropic:** descartada por costo.
- **Claude Code más un modelo local (Ollama) para el trabajo masivo:** descartada por el hardware disponible. Se puede reconsiderar para usuarios con GPU mediante un ADR nuevo.
- **Usar el LLM solo para guiar, con cribado 100 % humano:** descartada. El investigador quiere al LLM como revisor asistente, y medir su concordancia es un aporte metodológico.
- **Aplicación web local para el cribado (p. ej. Streamlit):** descartada por decisión del investigador. La hoja Excel cubre la revisión humana ciega.

## Consecuencias

- **La cuota del plan Pro es el recurso escaso.** Todo filtro que no requiera juicio (duplicados, años, idioma, tipo de documento) se aplica antes de llamar al LLM. El cribado con LLM se hace por lotes (del orden de 25 registros) y puede interrumpirse y retomarse.
- **La temperatura no se controla.** Claude Code no permite fijar la temperatura ni otros parámetros de muestreo. La reproducibilidad se apoya en el registro completo (ADR-0004), no en regenerar respuestas idénticas.
- **Los alias de modelo cambian con el tiempo.** El repositorio de cada estudio fija el identificador completo del modelo en la configuración de Claude Code, y cada decisión lo registra.
- **El agente depende de Claude Code.** Como el paquete es independiente, podría usarse con otro asistente de programación en el futuro.
