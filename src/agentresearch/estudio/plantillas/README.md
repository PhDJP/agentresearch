# {{titulo}}

Estudio de mapeo sistemático de la literatura conducido con [agentresearch](https://github.com/PhDJP/agentresearch), siguiendo a Kitchenham (proceso), Petersen et al. (2008, 2015; mapeo) y PRISMA-ScR (Tricco et al., 2018; reporte).

Este repositorio contiene los datos y la evidencia del estudio. La herramienta está en su propio repositorio, y este la fija a una versión exacta.

## Instalación

Requiere [uv](https://docs.astral.sh/uv/) y Git.

```powershell
uv sync
```

`uv sync` instala Python 3.12 y la versión de agentresearch que fija `pyproject.toml` (la que registra `estudio.yaml`), y crea o respeta `uv.lock`, que fija todas las dependencias y se versiona.

Para pasar el estudio a otra versión del agente: cambie la versión en `pyproject.toml`, ejecute `uv sync` y luego, en su terminal, `uv run agentresearch estudio actualizar --actualizado-por <id> --justificacion "…"`. El comando regenera las instrucciones del agente, muestra el diff, pide confirmación y registra la actualización. Haga el commit con el anclaje que muestra.

## Uso

1. Abra Claude Code en esta carpeta y acepte el diálogo de confianza del proyecto; sin él, no se aplican los permisos de `.claude/settings.json`.
2. Escriba `/protocolo` para construir el protocolo con el agente, sección por sección.
3. Los comandos que el agente no puede ejecutar (aprobar, enmendar y confirmar decisiones) se ejecutan en una terminal propia: PowerShell o la terminal de VS Code. En Windows, Git Bash abierto como aplicación independiente no ofrece la consola que exigen.

Ayuda de los comandos: `uv run agentresearch --help`.

## Estructura

| Ruta | Contenido |
|---|---|
| `estudio.yaml` | Metadatos del estudio, versión exacta del agente y modelo fijado |
| `protocolo/protocolo.yaml` | Protocolo del estudio |
| `protocolo/eventos.jsonl`, `protocolo/anclaje.json` | Registro encadenado de creación, aprobación, enmiendas y decisiones, y su anclaje |
| `protocolo/versiones/` | Copia exacta de cada versión registrada del protocolo |
| `protocolo/ecuaciones.md` | Ecuaciones de búsqueda por fuente |
| `protocolo/insumos/` | Insumos aportados por el investigador |
| `CLAUDE.md`, `.claude/` | Instrucciones del agente: reglas, modelo fijado, permisos y *skills* |

Las fases siguientes (búsquedas, importaciones, registros, cribado, bola de nieve, texto completo, extracción, análisis y reportes) crean sus carpetas cuando se ejecutan.

## Trazabilidad

El registro de eventos es una cadena de hashes, no una firma criptográfica. Su valor como evidencia viene de combinarlo con el historial de Git y con el depósito del repositorio en Zenodo. Para comprobarlo:

```powershell
uv run agentresearch registro verificar protocolo/eventos.jsonl
uv run agentresearch protocolo historial
```

## Licencia

Los datos de este estudio se publican con la licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). El material con derechos de autor (textos completos, exportaciones con restricciones) no se versiona.

Creado el {{fecha}}.
