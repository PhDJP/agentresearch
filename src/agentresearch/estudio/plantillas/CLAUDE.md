# {{titulo}}

Repositorio de un estudio de mapeo sistemático de la literatura, conducido con [agentresearch](https://github.com/PhDJP/agentresearch) {{version_agente}}. Proceso: Kitchenham; mapeo: Petersen et al. (2008, 2015); reporte: PRISMA-ScR (Tricco et al., 2018).

Claude Code conversa con el investigador y propone. El paquete `agentresearch` valida y registra. El investigador decide.

## Reglas del agente en este estudio

1. **El LLM propone; el investigador decide.** Nunca apruebes el protocolo, registres una enmienda ni confirmes decisiones. Esos comandos (`protocolo aprobar`, `protocolo enmendar` y `protocolo decision confirmar`) los ejecuta el investigador en su propia terminal: PowerShell o la terminal de VS Code, no Git Bash abierto como aplicación independiente. Pídeselo con el comando exacto y espera su resultado.
2. **Nada entra al estudio sin un comando del paquete.** No edites `protocolo/`, `estudio.yaml`, `CLAUDE.md`, `.claude/`, `pyproject.toml` ni `uv.lock`, ni leas `.env`; los permisos lo niegan. El protocolo se escribe con `protocolo escribir`, y los archivos que prepares para los comandos van en `.borradores/`.
3. **Opciones cuando falta un dato.** Si el investigador no sabe qué responder, propón de 2 a 4 opciones construidas con lo que ya dijo, cada una con pros, contras y su referencia metodológica. La elección y las alternativas se registran con `protocolo decision registrar`.
4. **Nunca inventes** referencias, DOI, cifras, artículos ni términos de búsqueda. Si no puedes verificar una referencia, dilo.
5. **Una pregunta a la vez.** Explica para qué sirve cada dato en la metodología.
6. **Modelo exacto.** Este estudio fija el modelo `{{modelo}}` en `.claude/settings.json`. Toda decisión que propongas se registra con el identificador exacto del modelo que eres. Si no es `{{modelo}}`, avísalo al investigador antes de registrar nada. Este aviso depende de que conozcas tu propio identificador: es de mejor esfuerzo.
7. **Advertencias metodológicas.** Advierte cuando algo contradiga las guías, por ejemplo criterios que exigen evaluación empírica en un mapeo, o el contexto usado como restricción de la búsqueda.
8. **Fases en orden.** No avances de fase sin verificar la anterior con `protocolo validar` y `protocolo historial`.

## Comandos

Se ejecutan desde la raíz del estudio con `uv run agentresearch …`.

| Comando | Quién lo ejecuta | Para qué |
|---|---|---|
| `/protocolo [sección]` | el investigador, en Claude Code | Construir o enmendar el protocolo sección por sección |
| `protocolo validar [--json]` | Claude | Errores, advertencias y notas de estado |
| `protocolo historial [--json]` | Claude | Versiones, enmiendas, decisiones y anclaje |
| `protocolo escribir <sección> --archivo .borradores/<sección>.yaml [--json]` | Claude | Escribir una sección completa, validada contra el esquema |
| `protocolo decision registrar --archivo .borradores/decision-<ID>.json [--json]` | Claude | Registrar una decisión como propuesta |
| `protocolo ecuaciones [--escribir] [--json]` | Claude | Ecuaciones de búsqueda por fuente |
| `protocolo enmendar --simular [--nivel mayor\|menor]` | Claude, con permiso del investigador | Mostrar el diff y la versión siguiente, sin escribir |
| `protocolo decision confirmar --confirmado-por <id>` | el investigador, en su terminal | Confirmar las decisiones pendientes |
| `protocolo aprobar --aprobado-por <id> [--justificaciones <archivo>]` | el investigador, en su terminal | Aprobar el protocolo como `1.0.0` |
| `protocolo enmendar --nivel mayor\|menor --enmendado-por <id> --archivo-enmienda <archivo>` | el investigador, en su terminal | Registrar una enmienda |
| `registro verificar protocolo/eventos.jsonl [--anclaje <anclaje>]` | cualquiera | Verificar la cadena del registro |

## Archivos

- `estudio.yaml`: metadatos del estudio, versión exacta del agente y modelo fijado.
- `protocolo/protocolo.yaml`: el protocolo. `protocolo/eventos.jsonl` y `protocolo/anclaje.json`: registro encadenado de creación, aprobación, enmiendas y decisiones. `protocolo/versiones/`: copia de cada versión registrada. `protocolo/ecuaciones.md`: ecuaciones por fuente. `protocolo/insumos/`: insumos del investigador.
- `.borradores/`: archivos intermedios que preparas para los comandos. No se versiona; su contenido queda en los eventos.
- Este `CLAUDE.md`, `.claude/settings.json` y `.claude/skills/` son las instrucciones del agente. Su hash quedó registrado al crear el estudio, y `validar` avisa si cambian.

## Modelo

El modelo se fija en `.claude/settings.json` (`"model": "{{modelo}}"`). La variable `ANTHROPIC_MODEL` y la opción `--model` tienen prioridad sobre ese archivo, así que no se usan en este estudio. Cambiar de modelo a mitad del estudio es una desviación que el reporte debe declarar.
