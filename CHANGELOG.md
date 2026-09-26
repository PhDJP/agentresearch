# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto sigue [versionado semántico](https://semver.org/spec/v2.0.0.html).

## [Sin publicar]

### Agregado

- Módulo `agentresearch.trazabilidad`: registro encadenado de eventos
  (`RegistroEncadenado`), un JSONL de solo adición con hashes SHA-256
  verificables, serialización JSON canónica, y reloj inyectable para
  pruebas deterministas.
- CLI `agentresearch registro verificar <archivo.jsonl>` (código 0 si la
  cadena es íntegra, 1 si no).
- Punto de entrada `python -m agentresearch` (`__main__.py`).
- ADR-0006 (propuesta): formato del protocolo y registro encadenado de
  eventos; la sección del registro encadenado ya está decidida.

### Corregido

- `CITATION.cff`: se agrega `repository-code`.
- Integración continua: `actions/checkout` y `astral-sh/setup-uv`
  actualizados a versiones con soporte nativo de Node.js 24 (sin el aviso de
  Node 20 deprecado), y la versión de uv en CI queda fijada a la misma del
  entorno local.

## [0.0.1] - 2026-09-25

### Agregado

- Documentación inicial del proyecto: arquitectura, hoja de ruta, reglas
  metodológicas y ADR 0001-0005.
- Paquete `agentresearch` en Python 3.12 con estructura `src/`, gestionado
  con uv.
- CLI mínima con `agentresearch --version`.
- Configuración de pytest, ruff y mypy estricto.
- Integración continua en GitHub Actions (Windows y Ubuntu).
- `LICENSE` (MIT) y `CITATION.cff`.
