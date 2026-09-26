# ADR-0008: Ciclo de vida del protocolo

- Estado: Aceptada
- Fecha: 2026-09-26
- Participantes: investigador doctoral y Claude Code

## Contexto

El sub-hito 1c de la
[especificación del hito 1](../especificaciones/hito_1_protocolo_y_trazabilidad.md)
convierte el protocolo validado de 1b en un documento con ciclo de vida:
se aprueba, se enmienda con fecha y justificación, y registra las decisiones
tomadas para construirlo (como O1 a O10 del caso piloto). Las reglas
metodológicas lo exigen: el protocolo lleva un registro de enmiendas con
fecha, cambio, justificación y efecto esperado
([reglas metodológicas](../metodologia/reglas_metodologicas.md), §2), y
PRISMA-ScR pide informar dónde consultar el protocolo (ítem 5) y reportar
las desviaciones (ítem 20).

Este ADR se apoya en dos decisiones aceptadas:

- el ADR-0006 fija el registro encadenado de eventos y el formato del
  protocolo. Su punto 10 reconoce que truncar el final del registro no se
  detecta sin un anclaje externo, y deja su formato a este ADR;
- la regla 1 de CLAUDE.md fija que el LLM propone y el investigador decide.
  Claude Code ejecuta los comandos del paquete, así que hace falta una
  barrera para que el LLM no apruebe, no enmiende ni confirme decisiones por
  su cuenta.

Las opciones de cada decisión se presentaron al investigador con pros y
contras, y él eligió (2026-09-26). Las no elegidas están en "Alternativas
consideradas".

## Decisión

### Archivos del protocolo en el estudio

1. **Directorio del protocolo.** Junto a `protocolo/protocolo.yaml` viven:

   ```text
   protocolo/
   ├── protocolo.yaml       # versión actual
   ├── eventos.jsonl        # registro encadenado del ciclo de vida (ADR-0006)
   ├── anclaje.json         # anclaje del registro (punto 20)
   └── versiones/
       ├── 1.0.0.yaml       # copia exacta de cada versión registrada
       └── 1.1.0.yaml
   ```

   Se localizan por convención, sin configuración: son hermanos del archivo
   del protocolo. El **estudio** es el directorio padre del directorio del
   protocolo.
2. **Rutas guardadas.** Toda ruta que se guarda en un evento o en
   `anclaje.json` es relativa al estudio, usa `/` como separador y no
   contiene `..`; nunca es absoluta (por ejemplo
   `protocolo/versiones/1.0.0.yaml`). Así el registro es el mismo en Windows
   y en Linux, y el estudio se puede mover o clonar.
3. **Lectura única.** Cada comando lee los bytes de `protocolo.yaml` una sola
   vez, y sobre esos mismos bytes valida, calcula el diff y calcula el hash.
   Así no hay una ventana en la que el archivo cambie entre la validación y
   el registro. Justo antes de escribir, comprueba que el archivo conserva
   esos bytes, por ejemplo que no se editó mientras el investigador
   confirmaba. Si cambió, cancela sin escribir nada.

### Estados y versiones

4. **Estados:** `borrador` → `vigente`, sin vuelta atrás.
   - En `borrador`, el protocolo se edita libremente: sus versiones son
     `0.y.z`, no se registran eventos de ciclo de vida y el historial de Git
     guarda sus cambios.
   - Desde la aprobación, el protocolo está `vigente` y todo cambio es una
     enmienda.
   - El estado efectivo lo determina el registro, no el campo `estado` del
     YAML, que se puede editar a mano. Si el registro contiene una
     aprobación, el protocolo está aprobado, diga lo que diga el archivo
     (regla P-E09, punto 23).
5. **Versión al aprobar.** `aprobar` fija siempre `1.0.0`. Un borrador debe
   tener versión `0.y.z`; si no, `aprobar` se niega.
6. **Versión al enmendar** (versionado semántico del protocolo):
   - **mayor** (`X+1.0.0`): el cambio puede alterar qué estudios se incluyen
     o cómo se clasifican los ya procesados. Por ejemplo: criterios, bloques
     de búsqueda, PCC, fuentes, regla de combinación A–F, o facetas y sus
     categorías;
   - **menor** (`X.Y+1.0`): aclaraciones o agregados que no invalidan
     decisiones ya tomadas;
   - **parche** (`X.Y.Z+1`): lo asigna el paquete, sin juicio, cuando el diff
     estructural sale vacío, es decir, cuando solo cambiaron comentarios,
     comillas o formato. En ese caso no se acepta `--nivel`.

   Fuera del parche, `--nivel mayor|menor` es obligatorio: clasificar el
   cambio es un juicio del investigador, y el diff registrado permite
   revisarlo.

### Eventos

7. **Tipos de evento** en `protocolo/eventos.jsonl`, con los campos comunes
   del ADR-0006 (`id`, `tipo`, `fecha_hora_utc`, `version_agente`, `datos`,
   `hash_anterior`, `hash`). Cada `datos` se valida con un esquema pydantic
   estricto al leerlo.

   | Tipo | `datos` |
   |---|---|
   | `protocolo_aprobado` | `version_anterior`, `version_protocolo` (`1.0.0`), `hash_revisado`, `hash_protocolo`, `ruta_protocolo`, `ruta_version`, `aprobado_por` (`{tipo: humano, id}`), `advertencias` (cada una con `id_regla`, `ubicacion`, `mensaje`, `referencia`, `justificacion` y `origen`: `archivo` o `terminal`) |
   | `protocolo_enmendado` | `version_anterior`, `version_protocolo`, `nivel` (`mayor`, `menor` o `parche`), `hash_protocolo_anterior`, `hash_revisado`, `hash_protocolo`, `ruta_protocolo`, `ruta_version`, `justificacion`, `efecto_esperado`, `enmendado_por` (`{tipo: humano, id}`), `cambios` (punto 13), `solo_formato`, `advertencias` (`id_regla`, `ubicacion`, `mensaje`, `referencia`) |
   | `decision_propuesta` | `decision` (el JSON de entrada ya validado, punto 16), `version_protocolo`, `estado_protocolo`, `hash_protocolo` |
   | `decision_confirmada` | `id_decision`, `evento_propuesta` (ID del evento `decision_propuesta`), `hash_evento_propuesta`, `confirmado_por` (`{tipo: humano, id}`) |

   El registro puede contener eventos de otros tipos, como el evento inicial
   que agregará el sub-hito 1e. El ciclo de vida los ignora, pero su cadena
   se verifica igual.
8. **Hashes del protocolo en los eventos.**
   - `hash_revisado`: hash de los bytes leídos, que el investigador revisó:
     el borrador al aprobar, o el archivo editado al enmendar.
   - `hash_protocolo`: hash de los bytes que se escriben, después de cambiar
     el estado o la versión. Se calcula en memoria sobre el texto que se va
     a escribir en UTF-8 con LF, así que coincide con `hash_archivo` del
     archivo resultante.
   - `hash_protocolo_anterior`: el `hash_protocolo` de la versión que se
     enmienda.

   El "último hash registrado" contra el que compara P-E09 es el
   `hash_protocolo` del último evento `protocolo_aprobado` o
   `protocolo_enmendado`. Las decisiones no lo cambian.

### Aprobar

9. **`agentresearch protocolo aprobar [ruta] --aprobado-por ID [--justificaciones archivo.json] [--json]`.**
   Se niega si:
   - hay algún error, de P-E00 a P-E10;
   - el estado no es `borrador`, o la versión no es `0.y.z`;
   - `--aprobado-por` no es un revisor de tipo `humano` declarado en
     `seleccion.revisores`;
   - hay decisiones pendientes de confirmar (punto 17);
   - no hay una terminal interactiva (punto 11).

   Si todo está en orden, pasa el estado a `vigente` y la versión a `1.0.0`,
   conservando comentarios y comillas (escritura por fusión del ADR-0006), y
   registra `protocolo_aprobado`.
10. **Justificación de cada advertencia.** Cada advertencia P-A activa
    necesita una justificación no vacía, que queda en el evento. La
    justificación puede venir de dos lados:
    - de un archivo `{"justificaciones": [{"id_regla", "ubicacion", "justificacion"}]}`,
      donde cada entrada se empareja con una advertencia por
      `(id_regla, ubicacion)`, los campos que ya da `protocolo validar --json`.
      Una entrada que no corresponde a ninguna advertencia activa, o una
      repetida, es un error;
    - de la confirmación interactiva, que pide las que falten. Una respuesta
      vacía cancela la aprobación.

    La confirmación muestra todas las justificaciones, incluidas las del
    archivo (que pudo proponer el LLM), antes de pedir la frase de
    confirmación.

### Confirmación interactiva: una barrera de procedimiento

11. **`aprobar`, `enmendar` y `decision confirmar` exigen una terminal
    interactiva.** Muestran un resumen completo (y el diff, al enmendar) y
    piden escribir una frase exacta: `aprobar 1.0.0`, `enmendar 1.1.0` o
    `confirmar N`, donde N es el número de decisiones. Si la entrada estándar
    no es una consola, se niegan sin leerla. El diálogo va a la salida de
    errores, para que la salida estándar quede limpia con `--json`.
    - **Cómo se detecta la consola.** En Windows, con `GetConsoleMode` sobre
      el manejador de la entrada estándar. En otros sistemas, con `isatty()`.
      En Windows, `isatty()` no basta: devuelve verdadero para el
      dispositivo `NUL`. Esto se verificó el 2026-09-26 en Claude Code sobre
      Windows 11, y la tabla de abajo recoge el resultado.
    - **Qué pasa hoy en Claude Code.** Sus herramientas no aceptan entrada
      interactiva: la entrada estándar es una tubería o el dispositivo nulo,
      y ninguno de los dos es una consola. El LLM no puede completar la
      confirmación desde sus herramientas, y el investigador ejecuta estos
      comandos en su propia terminal.
    - **No es una garantía.** Es una barrera de procedimiento. Depende de
      cómo funciona hoy la herramienta, y se puede eludir emulando una
      terminal (p. ej. con `script` en Linux o `winpty` en Windows). Su
      valor está en que la ruta normal del LLM no puede aprobar, y en que
      cada confirmación deja registrado un `aprobado_por`, `enmendado_por`
      o `confirmado_por` humano.
    - **Complementos previstos para 1e:** la plantilla del estudio podrá
      negar estos comandos en los permisos de Claude Code, y `/protocolo`
      pedirá al investigador que los ejecute él.

    | Entrada estándar observada | `isatty()` | `GetConsoleMode` |
    |---|---|---|
    | Herramienta Bash de Claude Code (tubería) | falso | falso |
    | Herramienta PowerShell de Claude Code (`NUL`) | verdadero | falso |
    | Redirección desde `NUL` | verdadero | falso |

### Enmendar

12. **`agentresearch protocolo enmendar [ruta] --nivel mayor|menor --enmendado-por ID (--justificacion T --efecto-esperado T | --archivo-enmienda enmienda.json) [--simular] [--json]`.**
    - `enmienda.json` tiene la forma `{"justificacion": "…", "efecto_esperado": "…"}`,
      y su contenido se muestra completo en la confirmación. Se da el
      archivo o las dos opciones, no ambos.
    - Se niega si:
      - el protocolo no está aprobado según el registro, o si su estado en
        el archivo no es `vigente`;
      - el archivo no cambió desde el último hash registrado;
      - la versión o el estado se editaron a mano (la versión la asigna el
        paquete);
      - la copia de la última versión falta o no coincide con su hash;
      - hay errores de P-E00 a P-E08 o P-E10;
      - hay una operación interrumpida (punto 23);
      - hay decisiones pendientes;
      - `--enmendado-por` no es un revisor humano declarado;
      - no hay una terminal interactiva.

      El P-E09 de "cambio sin enmienda registrada" es justamente lo que la
      enmienda resuelve, así que no la impide.
    - Registra `protocolo_enmendado` con las advertencias activas. A
      diferencia de la aprobación, no exige justificarlas.
    - `--simular` calcula el diff y la versión siguiente, y lista lo que
      impediría enmendar, sin escribir nada y sin exigir terminal. Sirve para
      que Claude Code muestre el diff al investigador antes de que este
      confirme.
13. **Diff estructural,** generado por el paquete y no por el LLM. Compara el
    modelo pydantic completo (con los valores por defecto) de la copia de la
    última versión con el del archivo actual. Así, escribir un valor por
    defecto explícito, reordenar claves o cambiar comentarios no cuenta como
    cambio de contenido.
    - Cada cambio es `{ruta, operacion, antes, despues}`, con `operacion`
      igual a `agregado`, `eliminado`, `modificado` o `reordenado`.
    - Las listas cuyos elementos tienen `id` se comparan por su `id`, y la
      ruta lo usa: `criterios.inclusion[CI2].texto`. Un cambio de orden entre
      los mismos `id` se reporta una vez como `reordenado`, con la lista de
      `id` antes y después.
    - Las listas de escalares (términos, direcciones, letras de la regla)
      se reportan completas en un solo cambio `modificado`, que además
      incluye `agregados` y `eliminados`, contados como multiconjunto.
    - Las demás listas (autores, artículos del conjunto de validación,
      cruces) se comparan por posición: `metadatos.autores[0].nombre`.
    - `solo_formato` es verdadero cuando la lista de cambios está vacía.

### Atomicidad

14. **El evento es el punto de confirmación.** `aprobar` y `enmendar`
    escriben en este orden:
    1. la copia `versiones/X.Y.Z.yaml`;
    2. el evento en `eventos.jsonl`;
    3. `anclaje.json`;
    4. `protocolo.yaml`.

    Los archivos 1, 3 y 4 se escriben en un temporal del mismo directorio,
    con `flush` y `os.fsync`, y luego se reemplazan con `os.replace`, que es
    atómico en Windows y en POSIX. `RegistroEncadenado.agregar()` también
    hace `flush` y `os.fsync` del evento. Todo esto ocurre antes de reemplazar
    `protocolo.yaml`. La sincronización del directorio no se hace, porque
    Windows no la admite.
15. **Qué pasa si falla a mitad.**
    - **Antes del evento:** no se confirmó nada. La copia, si llegó a
      escribirse, queda huérfana: ningún evento la referencia, se ignora y
      se sobrescribe en el siguiente intento. Hay una excepción: en la
      primera aprobación todavía no existe `eventos.jsonl`, así que una
      carpeta `versiones/` huérfana dispara P-E10. El investigador comprueba
      con Git que nunca hubo un registro y la elimina.
    - **Entre el evento y `anclaje.json`:** el anclaje queda un evento por
      detrás, y eso es válido porque se verifica como prefijo (punto 20). El
      siguiente comando lo pone al día.
    - **Entre el evento y `protocolo.yaml`:** el archivo conserva el hash
      revisado. P-E09 lo reconoce como una operación interrumpida e indica
      cómo recuperarse: copiar `versiones/X.Y.Z.yaml` sobre `protocolo.yaml`.
      La copia tiene exactamente el hash que registró el evento.

### Decisiones del protocolo, en dos pasos

16. **`agentresearch protocolo decision registrar --archivo decision.json [--protocolo ruta] [--json]`**
    registra `decision_propuesta`. Solo la impiden P-E00 y P-E10: los demás
    errores no, porque un borrador está incompleto mientras se construye. El
    esquema es el de la especificación,
    más un campo `reemplaza` opcional. Se valida con pydantic estricto: una
    clave desconocida, un tipo incorrecto o una clave repetida en el JSON son
    errores. Se reportan todos los errores a la vez:
    - entre 2 y 4 opciones, con `id` únicos y sin espacios;
    - cada opción tiene descripción y al menos un pro, un contra y una
      referencia no vacíos (regla 9 de CLAUDE.md);
    - `elegida` es el `id` de una de las opciones;
    - tema, pregunta y justificación no están vacíos;
    - `decidido_por.tipo` es `humano`, y su `id` es un revisor humano
      declarado en el protocolo;
    - si `propuesto_por.tipo` es `llm`, su `modelo` es un identificador
      exacto: sin espacios, con al menos un dígito, que no termina en
      `-latest` y que no es un alias (`opus`, `sonnet`, `haiku`, `fable`,
      `default`, `opusplan`, `best`, `claude`). Si es `humano`, lleva un
      `id` y no lleva `modelo`;
    - `id_decision` no está registrado antes;
    - `reemplaza`, si se da, es un `id_decision` registrado que ninguna otra
      decisión reemplaza todavía.

    El paquete no puede comprobar que una referencia bibliográfica exista
    (regla 6); solo exige que no esté vacía. Tampoco puede saber quién
    ejecutó el comando: por eso la decisión queda como propuesta hasta que el
    investigador la confirma.
17. **`agentresearch protocolo decision confirmar --confirmado-por ID [--protocolo ruta] [--json]`**
    exige terminal. Muestra completas las decisiones pendientes cuyo
    `decidido_por.id` es `ID` y, si el investigador escribe `confirmar N`,
    registra un `decision_confirmada` por cada una. `ID` debe ser un revisor
    humano declarado. Nadie confirma decisiones atribuidas a otra persona.
    Si no hay decisiones pendientes, termina sin exigir terminal.

    Cada decisión tiene un estado, que se deriva del registro:
    - **pendiente:** propuesta sin confirmar y sin reemplazar;
    - **confirmada;**
    - **reemplazada:** otra decisión la nombra en `reemplaza`.

    Para corregir una propuesta equivocada, se registra otra con
    `reemplaza`. `aprobar` y `enmendar` se niegan mientras haya decisiones
    pendientes.

### Historial y anclaje

18. **`agentresearch protocolo historial [ruta] [--json]`** muestra:
    - el estado y la versión actuales;
    - las versiones registradas, con su fecha, quién las aprobó o enmendó y
      su hash;
    - las enmiendas, con su nivel, justificación, efecto esperado y cambios;
    - las decisiones, con su estado;
    - la integridad de la cadena y el anclaje.

    Alimenta los ítems 5 y 20 de PRISMA-ScR. Sale con código 1 si hay
    P-E10, porque en ese caso el historial no es fiable. P-E09 lo muestra
    como una nota.
19. **Formato del anclaje:** `evt-NNNNNN@sha256:<hex>`, es decir, el ID del
    último evento (que codifica el número de eventos) y su hash. Un registro
    vacío tiene el anclaje `evt-000000@sha256:genesis`.
20. **Verificación como prefijo.** Un registro cumple un anclaje de N eventos
    si tiene al menos N eventos y el evento N tiene ese hash. Así, un
    anclaje que quedó atrás por un fallo sigue siendo válido, y un registro
    al que le quitaron eventos finales no lo cumple.
21. **Dónde se guarda el anclaje:**
    - en `protocolo/anclaje.json`, que actualiza cada comando después de
      registrar su evento:

      ```json
      {"hash_ultimo": "sha256:…", "numero_eventos": 7, "registro": "protocolo/eventos.jsonl"}
      ```

      Se escribe con claves ordenadas, sangría de 2 espacios, UTF-8 y LF;
    - en la salida de `historial` y en el bloque `registro` de
      `validar --json`, para copiarlo fuera del estudio, por ejemplo en el
      mensaje de un commit o en un depósito de Zenodo;
    - `agentresearch registro verificar archivo --anclaje evt-NNNNNN@sha256:…`
      compara un registro con un anclaje guardado fuera.

    Los comandos que escriben eventos se niegan si el registro no cumple
    `anclaje.json`. Si `anclaje.json` falta pero el registro existe, no es un
    error: el siguiente comando lo vuelve a crear. La evidencia de un borrado
    deliberado del anclaje y del final del registro a la vez es el historial
    de Git (ADR-0006, punto 9).

### Reglas que leen el directorio del estudio

22. **P-E09 y P-E10 no son reglas sobre el modelo.** Leen el directorio del
    estudio: el registro, el anclaje y las copias de versión. Por eso
    `validar_protocolo()` y `validar_documento()` no las evalúan, y
    `validar_archivo()` sí. Sus hallazgos no llevan ubicación en el
    protocolo; el mensaje nombra el archivo afectado.
23. **P-E09, "cambio sin enmienda registrada"** (error). Salta en dos casos:
    - hay una aprobación registrada y el hash actual del archivo difiere del
      último hash registrado, aunque el campo `estado` diga `borrador`. Si el
      hash actual es el `hash_revisado` del último evento, el mensaje
      identifica una operación interrumpida y da la instrucción de
      recuperación del punto 15;
    - el estado es `vigente`, pero no hay `eventos.jsonl` o no contiene
      ninguna aprobación.

    El primer caso solo necesita los bytes, así que se evalúa aunque haya
    P-E00. El segundo necesita el estado, así que no se evalúa si hay P-E00.
    Si hay P-E10, P-E09 no se evalúa, porque su referencia no es fiable.
    Referencia: reglas metodológicas, §2 (registro de enmiendas); PRISMA-ScR,
    ítem 20.
24. **P-E10, "registro de eventos del protocolo íntegro"** (error). Se
    evalúa aunque haya P-E00. Salta si:
    - falta `eventos.jsonl`, pero existen `anclaje.json` o `versiones/`;
    - la cadena está rota (ADR-0006, punto 7);
    - `anclaje.json` no es válido o el registro no lo cumple;
    - un evento del ciclo de vida no cumple su esquema, o la secuencia es
      incoherente: otra aprobación, una enmienda sin aprobación previa, una
      versión o un hash anterior que no encadena, o una confirmación de una
      propuesta inexistente o ya confirmada;
    - falta la copia de una versión registrada, no coincide con su hash o
      no está en `protocolo/versiones/X.Y.Z.yaml`.

    Referencia: ADR-0006, puntos 7 y 10.
25. **P-A09, "piloto de cribado sin tamaño definido"** (advertencia):
    `seleccion.piloto.tamano` es menor o igual que 0. Referencia: Ali y
    Petersen (2014); Petersen et al. (2015), figura 17.

### Salida de los comandos

26. Todos los comandos nuevos admiten `--json`. Salen con código 0 si la
    operación se completa, con 1 si se rechaza o se cancela, y con 2 si los
    argumentos no son válidos (argparse). La salida JSON va en ASCII escapado
    y tiene esta forma común:

    ```json
    {"comando": "protocolo aprobar", "exito": true, "errores": [], "version_agente": "…", "resultado": {}}
    ```

## Alternativas consideradas

- **Contenido anterior del diff:**
  - guardar el protocolo completo dentro de cada evento: cada línea del
    registro crecería a decenas de KB, dejaría de leerse bien y su diff en
    Git sería ruidoso;
  - recuperarlo de Git: el motor pasaría a depender de Git y de que la
    versión aprobada ya tenga commit, y las pruebas necesitarían
    repositorios.
- **Orden de escritura:**
  - escribir el YAML primero y el evento al final: si falla entre los dos
    pasos, queda un protocolo vigente sin evento y sin nada fiable desde
    dónde reconstruirlo;
  - no fijar orden y solo detectar: deja al investigador reparando a mano.
- **Versiones:**
  - `--nivel` opcional con `menor` por defecto: un cambio mayor podría
    registrarse como menor por omisión;
  - versión escrita a mano: propensa a errores y no determinista;
  - que el paquete sugiera el nivel según las rutas del diff: se deja para
    más adelante.
- **Barrera contra la aprobación por el LLM:**
  - solo `--confirmo`, como decía la especificación: el LLM puede escribirlo
    igual que el humano, y no registra quién aprobó. Este ADR lo reemplaza
    por la confirmación interactiva;
  - solo `--aprobado-por`: registra la atribución, pero no impide nada;
  - comprobar la terminal con `isatty()` en todos los sistemas: en Windows
    acepta el dispositivo `NUL`, así que no detecta la herramienta
    PowerShell de Claude Code.
- **Decisiones en un paso,** registradas directamente como tomadas: el
  paquete no puede distinguir si el comando lo ejecutó el investigador o el
  LLM. Dos pasos permiten que el LLM escriba el registro y el investigador
  confirme en lote, con una sola interacción en la terminal para varias
  decisiones.
- **Validaciones de las decisiones:**
  - pros, contras y referencias como advertencias: debilitan la regla 9;
  - solo las validaciones de la especificación: el paquete no haría cumplir
    la regla 9.
- **Anclaje:**
  - solo mostrarlo, sin `anclaje.json`: depende de que el investigador lo
    guarde en cada operación;
  - solo `anclaje.json`, sin mostrarlo: no cumple la especificación, y no
    permite comparar con un anclaje guardado fuera.
- **Reglas de directorio:**
  - una opción `--eventos` en `validar`: agrega un modo de apuntar al
    registro equivocado, y la convención basta;
  - reportar la cadena rota dentro de P-E09: un ID de regla significaría
    dos cosas distintas (ADR-0006, punto 17).
- **Exigir `anclaje.json` cuando existe el registro:** un fallo entre el
  evento y el anclaje dejaría el estudio bloqueado sin un comando que lo
  repare.

## Consecuencias

- El investigador aprueba, enmienda y confirma decisiones en su propia
  terminal: PowerShell, cmd, Windows Terminal, la terminal de VS Code, o
  cualquier terminal de Linux o macOS. En Windows, Git Bash abierto en
  mintty no ofrece una consola a Python, así que no sirve para estos
  comandos. Claude Code prepara los archivos (decisiones, justificaciones y
  enmienda) y muestra el diff con `--simular`; el investigador revisa y
  confirma.
- El sub-hito 1e debe:
  - crear, con `nuevo-estudio`, `eventos.jsonl` con su evento inicial y el
    `anclaje.json` correspondiente;
  - hacer que `/protocolo` pida al investigador ejecutar `aprobar`,
    `enmendar` y `decision confirmar`;
  - valorar negar esos comandos en los permisos de Claude Code del estudio.
- La barrera de confirmación depende de cómo funcionan hoy las herramientas
  de Claude Code. Si una versión futura les da una consola interactiva, hay
  que revisarla en un ADR nuevo.
- `RegistroEncadenado.agregar()` ahora hace `os.fsync`. Escribir es un poco
  más lento, pero en el ciclo de vida del protocolo hay pocos eventos. La
  escritura por lotes del hito 5 debe tenerlo en cuenta.
- Las copias en `versiones/` duplican el protocolo en el repositorio del
  estudio, a cambio de que cada versión se pueda consultar por sí sola
  (PRISMA-ScR, ítem 5) y de que se pueda recuperar una operación
  interrumpida.
- El anclaje en `anclaje.json` detecta el truncamiento accidental del
  registro, no el deliberado: quien trunque a propósito puede editar ambos
  archivos. La evidencia de fondo sigue siendo Git más Zenodo (ADR-0006,
  punto 9), y los reportes deben declararlo.
- Una enmienda no exige justificar las advertencias. Si una enmienda
  introduce una advertencia nueva, queda registrada sin justificación. Se
  reevaluará con el uso.
