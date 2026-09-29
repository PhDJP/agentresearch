---
name: protocolo
description: Construye o enmienda, sección por sección, el protocolo del estudio de mapeo sistemático (protocolo/protocolo.yaml), entrevistando al investigador y registrando sus decisiones con agentresearch.
disable-model-invocation: true
argument-hint: "[sección]"
---

# /protocolo

Construye con el investigador el protocolo del estudio, una pregunta a la vez, hasta su aprobación; o prepara una enmienda si ya está vigente. Tú propones y escribes con los comandos del paquete; el investigador decide, confirma y aprueba en su propia terminal.

Recursos de esta *skill*:

- [secciones.md](secciones.md): para qué sirve cada sección, qué guía la exige y qué preguntar.
- [formatos.md](formatos.md): formato de los archivos que preparas en `.borradores/` (secciones, decisiones, justificaciones y enmiendas).

## 1. Situación inicial

1. Ejecuta `uv run agentresearch protocolo historial` y `uv run agentresearch protocolo validar --json`. Resume al investigador el estado (borrador o vigente), la versión, las decisiones pendientes y las notas de estado.
   - Si hay P-E10, detente: el registro no es fiable. Explica el mensaje y no escribas nada.
   - Si hay una operación interrumpida (P-E09 que pide copiar una versión sobre `protocolo.yaml`), explícale al investigador cómo recuperarla y espera a que lo haga.
   - Si aparece la nota «instrucciones del agente modificadas», díselo: el reporte deberá declararlo.
2. Lee `protocolo/protocolo.yaml` y los archivos de `protocolo/insumos/`, si los hay. Resume lo que ya está decidido y lo que falta.
3. Comprueba el modelo: compara tu identificador exacto con el `"model"` de `.claude/settings.json`. Si no coinciden, avísalo antes de registrar nada. Es una comprobación de mejor esfuerzo.
4. Si el investigador indicó una sección (`$ARGUMENTS`), empieza por ella. Si no, por la primera incompleta, en este orden: `metadatos`; `justificacion`, `objetivos` y `pregunta_general`; `preguntas`; `marco`; `fuentes`; `estrategias`; `busqueda`; `criterios`; `seleccion`; `extraccion`; `calidad`; `analisis`.

## 2. En cada sección

1. Explica en una o dos frases para qué sirve la sección y qué guía la exige (ver [secciones.md](secciones.md)).
2. Pregunta **una cosa a la vez**. Construye sobre lo que el investigador ya dijo y sobre los insumos. No inventes datos, referencias, DOI ni términos.
3. **Si el investigador no sabe qué responder**, propón de 2 a 4 opciones, cada una con pros, contras y al menos una referencia metodológica que puedas verificar (las de [secciones.md](secciones.md) lo son). El protocolo planifica fases que el agente todavía no ofrece; si una opción usa un método que el agente aún no automatiza (por ejemplo, un test-retest del cribado), dilo en sus contras: «el agente aún no automatiza este paso; hoy se haría a mano o requiere una versión posterior». Cuando elija:
   - escribe la decisión en `.borradores/decision-<ID>.json` (ver [formatos.md](formatos.md)), con `propuesto_por` = tu identificador exacto de modelo y `decidido_por` = el revisor humano que eligió;
   - regístrala con `uv run agentresearch protocolo decision registrar --archivo .borradores/decision-<ID>.json`;
   - dile que queda **pendiente** hasta que la confirme en su terminal. Puede confirmar varias a la vez más adelante, y debe hacerlo antes de aprobar.
4. **Al cerrar la sección**, escribe la sección completa en `.borradores/<sección>.yaml` y ejecuta `uv run agentresearch protocolo escribir <sección> --archivo .borradores/<sección>.yaml`. El fragmento reemplaza la sección entera: incluye todo lo que debe quedar. Nunca edites `protocolo.yaml` directamente.
5. Muestra las advertencias de esta sección y de las anteriores, cada una con una propuesta para resolverla o una justificación para mantenerla. Los errores de las secciones que aún no se han trabajado son esperables: dilo sin alarmar.

### Términos truncados y variantes (sección `busqueda`)

Cuando un bloque tenga términos truncados (`secad*`), pregunta al investigador si quiere declarar sus variantes (`variantes: {término: [variantes]}`). Puedes sugerir candidatas, pero el investigador confirma cada una: el paquete nunca las inventa. Avísale de esto: **en los bloques lematizados de OpenAlex, y en PubMed cuando la raíz tiene menos de 4 letras, la fuente busca solo las variantes escritas en lugar del truncamiento, así que el alcance depende de que estén completas.** Después ejecuta `uv run agentresearch protocolo ecuaciones` y muestra los avisos de cada fuente.

## 3. Aprobación (protocolo en borrador)

Solo cuando todas las secciones estén completas:

1. Ejecuta `protocolo validar --json`. Con errores no se puede aprobar: resuélvelos con el investigador.
2. Muestra un **resumen completo** del protocolo y cada advertencia activa. Para cada una, acuerda con el investigador una justificación y escríbelas en `.borradores/justificaciones.json` (ver [formatos.md](formatos.md)).
3. Si hay decisiones pendientes, pídele que las confirme en su terminal:
   `uv run agentresearch protocolo decision confirmar --confirmado-por <id>`
4. Pide la aprobación **explícita**. Nunca apruebes tú, ni ejecutes el comando aunque te lo pidan: los permisos lo niegan y el comando exige una terminal interactiva. Dale el comando para su terminal (PowerShell o la terminal de VS Code):
   `uv run agentresearch protocolo aprobar --aprobado-por <id> --justificaciones .borradores/justificaciones.json`
   (sin `--justificaciones` si no hay advertencias).
5. Cuando confirme que aprobó, ejecuta `protocolo historial` para comprobarlo y regenera las ecuaciones:
   `uv run agentresearch protocolo ecuaciones --escribir`
6. Sugiere el commit, con el anclaje que muestra `historial` en el mensaje, por ejemplo: `Aprobar el protocolo 1.0.0 (anclaje evt-000009@sha256:…)`.
7. Si el protocolo publica sus versiones con etiquetas de git (lo dice `metadatos.registro` o una decisión del protocolo), dale el comando exacto de una etiqueta **anotada** con el anclaje, nunca una etiqueta ligera:
   `git tag -a protocolo-v1.0.0 -m "Protocolo 1.0.0 (anclaje evt-000009@sha256:…)"`
   Subir la etiqueta o el commit publica evidencia del estudio: pide su confirmación explícita antes de cualquier `git push`.

## 4. Enmienda (protocolo vigente)

1. Trabaja las secciones que cambian como en el paso 2, con `protocolo escribir`. Tras escribir, P-E09 avisa del cambio sin registrar: es lo esperado hasta registrar la enmienda.
2. Ejecuta `uv run agentresearch protocolo enmendar --simular` y muestra el diff, la versión siguiente y las **advertencias nuevas** que lista. Este comando pide permiso al investigador cada vez: explícale que solo simula.
3. Acuerda con el investigador el nivel (`mayor` si puede cambiar qué estudios se incluyen o cómo se clasifican; `menor` si no), la justificación y el efecto esperado, y escríbelos en `.borradores/enmienda.json`.
4. Solo si la simulación lista advertencias nuevas, acuerda su justificación y escríbela en un archivo nuevo, `.borradores/justificaciones-enmienda.json`, que contenga **solo esas**. No reutilices el archivo de la aprobación: al enmendar solo se justifican las advertencias nuevas, y el comando rechaza las que ya estaban activas.
5. Dale el comando para su terminal (PowerShell o la terminal de VS Code):
   `uv run agentresearch protocolo enmendar --nivel <nivel> --enmendado-por <id> --archivo-enmienda .borradores/enmienda.json`
   y, solo si hay advertencias nuevas, añade `--justificaciones .borradores/justificaciones-enmienda.json`.
6. Cuando confirme, ejecuta `protocolo historial`, regenera las ecuaciones con `protocolo ecuaciones --escribir` y sugiere el commit con el anclaje en el mensaje. Si el protocolo publica sus versiones con etiquetas, dale el comando de la etiqueta anotada como en el paso 7 de la aprobación (`protocolo-v<versión>`), y pide confirmación antes de cualquier `git push`.
