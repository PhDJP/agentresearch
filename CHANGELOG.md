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
- Módulo `agentresearch.protocolo`:
  - modelo pydantic del protocolo, versión de esquema 1, que valida la
    forma (claves, tipos y valores permitidos) y admite borradores
    incompletos;
  - lectura y escritura en YAML con ruamel.yaml, conservando comentarios y
    comillas, con ida y vuelta idéntica byte a byte y fusión de las listas
    con `id` por su `id`;
  - plantilla comentada del protocolo;
  - validación con errores P-E00 a P-E08 y advertencias P-A01 a P-A08, cada
    una con ID estable, ubicación, línea y columna, y referencia
    metodológica.
- CLI `agentresearch protocolo validar [ruta] [--json]` (código 1 si hay
  errores, 0 si solo hay advertencias). La salida JSON incluye la versión
  del agente y el hash del archivo.
- Dependencias: pydantic y ruamel.yaml (ambas MIT).
- ADR-0006 aceptado: formato del protocolo y registro encadenado de
  eventos. El ciclo de vida del protocolo (sub-hito 1c) se decidirá en el
  ADR-0008.
- Integración continua: cobertura mínima del 90 % en `trazabilidad` y
  `protocolo`.
- Ciclo de vida del protocolo (sub-hito 1c, ADR-0008):
  - `protocolo aprobar --aprobado-por ID [--justificaciones archivo.json]`:
    pasa un borrador sin errores a vigente en la versión 1.0.0. Exige una
    justificación por cada advertencia activa y que no haya decisiones
    pendientes;
  - `protocolo enmendar --nivel mayor|menor --enmendado-por ID`, con
    justificación y efecto esperado (como opciones o con
    `--archivo-enmienda`): registra la enmienda con un diff estructural
    campo por campo e incrementa la versión. El parche lo asigna el
    paquete cuando solo cambian comentarios o formato. Exige justificar las
    advertencias nuevas, que no estaban activas en la versión registrada
    anterior (con `--justificaciones` o en la terminal). `--simular`
    muestra el diff y las advertencias nuevas sin escribir;
  - `protocolo decision registrar --archivo decision.json` y
    `protocolo decision confirmar --confirmado-por ID`: decisiones del
    protocolo en dos pasos (propuesta y confirmación en lote). Cada opción
    lleva pros, contras y referencias; decide un revisor humano declarado,
    y un LLM se identifica con el identificador exacto del modelo;
  - `protocolo historial`: versiones, enmiendas, decisiones y el anclaje
    del registro;
  - `aprobar`, `enmendar` y `decision confirmar` exigen una consola
    interactiva (`GetConsoleMode` en Windows, `isatty` en otros sistemas)
    y una frase exacta. Es una barrera de procedimiento para que el LLM no
    los complete desde sus herramientas, no una garantía. El mensaje de
    rechazo advierte que Git Bash independiente (mintty) no ofrece consola;
  - escritura atómica, con el evento como punto de confirmación: la copia
    de la versión, el evento, el anclaje y el protocolo, en ese orden y
    con `fsync`. Una operación interrumpida se reconoce y se recupera con
    la copia de `protocolo/versiones/`;
  - todos los comandos admiten `--json`, con una salida común
    (`comando`, `exito`, `errores`, `version_agente`, `resultado`).
- Anclaje del registro encadenado (`evt-NNNNNN@sha256:<hex>`), verificado
  como prefijo y guardado en `protocolo/anclaje.json`. Detecta la
  eliminación de eventos finales. `registro verificar --anclaje` compara
  un registro con un anclaje guardado fuera. Si `anclaje.json` falta, el
  comando que lo vuelve a crear lo informa (`"anclaje_recreado": true` en
  `--json`), y `validar` e `historial` lo avisan mientras falte.
- Reglas nuevas: P-E09 (cambio sin enmienda registrada; mira el registro
  y no solo el campo `estado`), P-E10 (registro íntegro, coherente,
  conforme a su anclaje y con sus copias de versión) y la advertencia
  P-A09 (piloto de cribado sin tamaño definido). P-E09 y P-E10 leen el
  directorio del estudio y se evalúan aunque haya P-E00.
- ADR-0008 aceptado: ciclo de vida del protocolo.
- Ecuaciones de búsqueda por fuente (sub-hito 1d, ADR-0009):
  - `protocolo ecuaciones [ruta] [--escribir] [--json]`: traduce los
    bloques del protocolo para las fuentes declaradas (OpenAlex, PubMed,
    Scopus y Web of Science) y una ecuación genérica, y guarda
    `protocolo/ecuaciones.md` de forma determinista. Para las fuentes
    manuales incluye los pasos de ejecución y exportación;
  - sintaxis verificada contra la documentación oficial de cada fuente,
    con la URL y la fecha en cada traductor. Lo que una fuente no admite
    usa las variantes que escribe el investigador (`variantes`, un campo
    opcional por bloque) o bloquea esa fuente con un aviso;
  - error P-E11 (término de búsqueda no traducible) y nota de estado de
    ecuaciones desactualizadas en `validar` e `historial`;
  - OpenAlex busca en título y resumen, verificado con consultas reales a
    la API: cada bloque es un filtro con su propio modo, los términos con
    guion van entre comillas, y un bloque con palabras vacías en frases o
    guiones, o con truncados sin variantes, usa la búsqueda exacta;
  - en Scopus, los términos con guion van entre comillas.
- ADR-0009 aceptado: ecuaciones de búsqueda por fuente.
- Repositorio de estudio y comando `/protocolo` (sub-hito 1e, ADR-0007):
  - `nuevo-estudio <ruta> --titulo T --modelo ID [--contexto archivo]`:
    crea el repositorio de un estudio desde las plantillas del paquete
    (`estudio.yaml`, proyecto uv fijado a la etiqueta de la versión del
    agente, protocolo en borrador, `CLAUDE.md`, `.claude/settings.json`,
    la *skill* `/protocolo`, `.gitignore`, `.gitattributes` y `README.md`)
    y registra el evento `estudio_creado` con el hash de cada archivo;
  - *skill* `/protocolo`: construye o enmienda el protocolo sección por
    sección, registra las decisiones y pide al investigador aprobar,
    enmendar y confirmar en su propia terminal;
  - configuración de Claude Code del estudio: modelo exacto fijado; niega
    `aprobar` y `decision confirmar`, pregunta antes de `enmendar` y niega
    editar el protocolo, el registro y las instrucciones del agente;
  - `protocolo escribir <sección> --archivo fragmento.yaml`: escribe una
    sección validando antes el esquema, también con el protocolo vigente;
  - nota de estado «instrucciones del agente modificadas» en `validar` e
    `historial`, y la creación del estudio en `historial`;
  - `estudio actualizar --actualizado-por ID (--justificacion T | --archivo A)`:
    pasa el estudio a la versión instalada del agente, regenera desde las
    plantillas sus instrucciones, `.gitignore` y `.gitattributes`
    (conservando el modelo fijado), muestra el diff, exige terminal
    interactiva y un revisor humano, y registra `estudio_actualizado`. Si
    la escritura se interrumpe, volver a ejecutarlo la completa;
  - el estudio niega a Claude Code leer `.env` y editar `pyproject.toml` y
    `uv.lock`, y su `.gitignore` versiona `.env.ejemplo`.

### Cambiado

- `protocolo validar` lee los bytes del protocolo una sola vez, y su
  salida incluye un resumen del registro de eventos con su anclaje.
- `RegistroEncadenado.agregar()` sincroniza cada evento a disco con
  `os.fsync`.
- El evento `estudio_creado` se valida con su esquema y solo puede ser el
  primero del registro (P-E10).
- En POSIX, la escritura atómica sincroniza el directorio después de
  `os.replace`, y el registro encadenado lo hace al crear su archivo, para
  que los nombres nuevos sobrevivan a un corte de energía. En Windows, que
  no lo admite, se sigue omitiendo.
- Integración continua: los sistemas quedan fijados en `ubuntu-24.04` y
  `windows-2025`, en vez de `ubuntu-latest` y `windows-latest`, para que el
  entorno de pruebas no cambie sin una decisión explícita.

### Corregido

- `CITATION.cff`: se agrega `repository-code`.
- La escritura del protocolo restaura los comentarios de sección de primer
  nivel, que ruamel.yaml perdía al vaciar una sección o dejaba fuera de
  lugar al agregarle un elemento al final (límite del ADR-0006).
- `RegistroEncadenado.verificar()` informa una línea JSON que no es un
  objeto, en vez de fallar con una excepción.
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
