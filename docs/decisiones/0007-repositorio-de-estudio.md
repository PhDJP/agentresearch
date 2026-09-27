# ADR-0007: Repositorio de estudio, comando `/protocolo` y estrategia de validación

- Estado: Propuesta
- Fecha: 2026-09-27
- Participantes: investigador doctoral, asesor (Claude en Cowork) y Claude Code

## Contexto

El sub-hito 1e de la
[especificación del hito 1](../especificaciones/hito_1_protocolo_y_trazabilidad.md)
cierra el hito: un investigador crea el repositorio de su estudio, construye
el protocolo con la guía de Claude Code, lo valida, lo aprueba y deja
trazada cada decisión. El ADR-0008 (Consecuencias) le encargó además:

- crear, con `nuevo-estudio`, el registro con su evento inicial y el anclaje;
- hacer que `/protocolo` pida al investigador ejecutar `aprobar`, `enmendar`
  y `decision confirmar`;
- valorar negar esos comandos en los permisos de Claude Code del estudio.

El ADR-0006 (Consecuencias) dejó un límite conocido de ruamel.yaml: al
escribir, el comentario de una sección de primer nivel se pierde o queda
fuera de lugar. `/protocolo` escribe sección por sección, así que hay que
resolverlo.

El 2026-09-27 el investigador y el asesor cambiaron además la estrategia de
validación del proyecto (punto 1). Las opciones de cada decisión se
presentaron con pros y contras, y el asesor y el investigador eligieron
(2026-09-27). Las no elegidas están en «Alternativas consideradas».

## Decisión

### Estrategia de validación

1. **Primero se termina el agente y después se usa en el caso piloto.**
   - Cada hito se acepta con un **estudio de demostración**: un tema real y
     neutral, distinto del caso piloto y de pocos registros, que recorre el
     flujo completo hasta ese hito. Sus datos nunca son los del caso piloto.
   - El caso piloto se ejecuta en el **hito 11**, con el agente terminado, y
     da la versión `v1.0.0`. El hito 10 cierra como `v0.10.0`.
   - Así, el protocolo de la tesis se construye una sola vez con la
     herramienta completa, y las mejoras del agente durante el desarrollo no
     generan enmiendas en él.
   - Riesgo aceptado: lo que solo aparece con datos reales se descubre al
     final. Se mitiga con un estudio de demostración realista y con las
     exportaciones reales de prueba del hito 2, y se corrige con versiones
     de parche (`v1.0.x`).

   El detalle está en la hoja de ruta («Estrategia de validación»).

### Estudio de demostración

2. **Tema: el mucílago de café** (obtención, caracterización y usos). Es un
   tema agroindustrial real, cercano al contexto del investigador y distinto
   del caso piloto. Su tamaño se estimó el 2026-09-27 con la API de OpenAlex,
   sin clave, en título y resumen: 97 registros con `"coffee mucilage"` y 395
   con `mucilag*` y `coffee` en la búsqueda exacta. También pone a prueba lo
   que resolvió el 1d: truncados con variantes, términos con guion y palabra
   vacía (`"coffee by-product*"`), tildes y frases.

   Tiene la misma forma que el caso piloto (subproducto: obtención,
   propiedades y aplicaciones), y eso lo hace realista. **Ninguna decisión del
   estudio de demostración se traslada al caso piloto**: en el hito 11 se
   toman de nuevo con `/protocolo`.
3. **Sus datos viven en un repositorio aparte y público**
   (`PhDJP/demo-mucilago-cafe`). Sigue la regla de un repositorio por
   estudio y prueba la instalación fijada a una etiqueta. Es público porque
   no contiene nada inédito, y lo pueden revisar el asesor y los jurados.
   Las pruebas de este repositorio siguen usando datos sintéticos.

### Estructura del repositorio de estudio

4. **`agentresearch nuevo-estudio <ruta> --titulo T --modelo ID [--contexto archivo] [--json]`**
   crea, desde las plantillas del paquete (`agentresearch/estudio/plantillas/`):

   ```text
   mi-estudio/
   ├── estudio.yaml                  # metadatos, versión exacta del agente y modelo fijado
   ├── pyproject.toml                # proyecto uv que fija el agente (punto 7)
   ├── README.md
   ├── CLAUDE.md                     # reglas del agente en el estudio
   ├── .claude/
   │   ├── settings.json             # modelo fijado y permisos (puntos 14 a 16)
   │   └── skills/protocolo/         # SKILL.md, secciones.md y formatos.md (punto 11)
   ├── .gitignore                    # .env, .venv/, .borradores/, PDF, material con derechos
   ├── .gitattributes                # * text=auto eol=lf
   └── protocolo/
       ├── protocolo.yaml            # desde la plantilla, con el título
       ├── eventos.jsonl             # con el evento estudio_creado (punto 9)
       ├── anclaje.json
       └── insumos/                  # solo con --contexto: copia exacta del insumo
   ```

   - **Solo crea `protocolo/`.** Las carpetas de las fases siguientes
     (búsquedas, importaciones, cribado, etc.) las crea cada hito cuando las
     use; el README del estudio las anuncia. Esto se aparta de la letra de
     la especificación («crea la estructura de carpetas»), pero evita
     archivos vacíos para versionar carpetas y fijar nombres antes de sus
     ADR.
   - **`.gitattributes` con `* text=auto eol=lf`,** para que Git para
     Windows no convierta los fines de línea y los hashes coincidan entre
     sistemas.
   - **`.borradores/`,** que no se versiona, guarda los archivos intermedios
     que prepara Claude Code (secciones, decisiones, justificaciones,
     enmiendas). Su contenido queda en el protocolo o en los eventos.
5. **Nombre del estudio.** Es el nombre de la carpeta en minúsculas, y
   también el del proyecto uv. Solo admite letras sin tilde, dígitos,
   puntos, guiones y guiones bajos, y empieza y termina con letra o dígito.
6. **Creación sin efectos a medias.**
   - Todo se arma en un directorio temporal junto al destino, con escritura
     atómica, y se renombra al final. Si algo falla, no queda nada.
   - El destino no debe existir o debe ser un directorio vacío.
   - `nuevo-estudio` no ejecuta Git ni uv ni usa la red. Muestra los pasos
     siguientes: `uv sync`, `git init`, el primer commit con el anclaje en el
     mensaje, el repositorio privado en GitHub y `/protocolo`. Así el paquete
     no depende de Git, como se decidió en el ADR-0008.
   - Se reportan todos los problemas de los argumentos a la vez.

### Instalación reproducible del agente

7. **El estudio es un proyecto uv** (`[tool.uv] package = false`) que
   depende de `agentresearch @ git+https://github.com/PhDJP/agentresearch@v<versión>`,
   y su `uv.lock` se versiona.
   - La etiqueta se deduce de la versión del paquete que crea el estudio:
     `v` más la versión PEP 440. Por eso cada versión publicada lleva su
     etiqueta.
   - `estudio.yaml` guarda esa versión y esa fuente, además del nombre, el
     título, la fecha de creación, el modelo fijado y la licencia de los
     datos (CC BY 4.0).
8. **Antes de `v0.1.0`,** el estudio de demostración se fija a una
   **etiqueta candidata, `v0.1.0rc1`**, con la versión `0.1.0rc1` en el
   paquete. Así los eventos registran una versión verdadera y distinguible
   de la final. Cuando se publique `v0.1.0`, el estudio pasa a esa etiqueta
   con un commit visible. Las versiones anteriores a `0.1.0rc1` decían
   `0.0.1` aunque el código fuera posterior; desde aquí, cada etiqueta
   corresponde a la versión del paquete.

### Evento inicial e instrucciones del agente

9. **Evento `estudio_creado`.** Es el primer evento de
   `protocolo/eventos.jsonl` y sus `datos` son:
   - `nombre`, `titulo`, `modelo` y `fuente_agente`;
   - `archivos`: la ruta y el hash de `estudio.yaml`, `pyproject.toml`, el
     protocolo, `README.md`, `.gitignore` y `.gitattributes`;
   - `instrucciones`: la ruta y el hash de `CLAUDE.md`,
     `.claude/settings.json` y cada archivo de `.claude/skills/`;
   - `insumos`: la ruta y el hash de lo copiado con `--contexto`.

   Se valida con un esquema pydantic estricto. Si no es el primer evento o
   no cumple su esquema, lo reporta P-E10. Los demás tipos desconocidos se
   siguen ignorando, como decía el ADR-0008 (punto 7).

   Un efecto secundario útil: como el registro existe desde la creación,
   una primera aprobación interrumpida ya no deja una carpeta `versiones/`
   sin registro que dispare P-E10; la copia huérfana se ignora como en
   cualquier otra operación.
10. **Nota «instrucciones del agente modificadas».**
    - `validar` e `historial` comparan las instrucciones registradas con los
      archivos actuales. Si alguno cambió, falta o se agregó, muestran esta
      nota de estado, y en `--json` `instrucciones_modificadas: true`.
    - Es una nota y no una advertencia P-A: no impide aprobar ni exige
      justificación, igual que la de ecuaciones desactualizadas del
      ADR-0009 (punto 14). El protocolo sigue siendo válido, pero el reporte
      debe poder decir con qué instrucciones trabajó el agente.
    - `.claude/settings.local.json` no cuenta: es local y no se versiona.
    - Registrar una actualización deliberada de las instrucciones con sus
      nuevos hashes queda para un hito posterior (hoja de ruta). Hasta
      entonces, el cambio se deshace con Git o se declara en el reporte.

### `/protocolo` como *skill* de Claude Code

11. **`/protocolo` es una *skill*** en `.claude/skills/protocolo/`.
    - La documentación de Claude Code (code.claude.com/docs/en/skills,
      consultada el 2026-09-27) dice que los comandos personalizados se
      fusionaron con las *skills*: `.claude/commands/x.md` y
      `.claude/skills/x/SKILL.md` crean el mismo `/x`, pero recomienda las
      *skills* para trabajo nuevo porque admiten archivos de apoyo.
    - `SKILL.md` lleva el flujo, y dos archivos de apoyo se cargan solo
      cuando hacen falta: `secciones.md` (para qué sirve cada sección, qué
      guía la exige, qué preguntar, sus reglas y las referencias del
      proyecto) y `formatos.md` (los archivos de `.borradores/`).
    - `disable-model-invocation: true`: solo el investigador la lanza.
      Claude no la carga por su cuenta.
12. **Flujo de `/protocolo`.** Es el de la especificación, más lo siguiente:
    - al empezar, revisa `historial` y `validar`: se detiene con P-E10,
      explica cómo recuperar una operación interrumpida y menciona la nota
      de instrucciones modificadas;
    - pide al investigador que ejecute `aprobar`, `enmendar` y
      `decision confirmar` en su propia terminal (PowerShell o la terminal
      de VS Code, no Git Bash independiente), con el comando exacto;
    - después de aprobar o enmendar, regenera las ecuaciones con
      `ecuaciones --escribir` y sugiere poner el anclaje en el mensaje del
      commit;
    - al pedir variantes de un truncado, avisa que en los bloques
      lematizados de OpenAlex, y en PubMed cuando la raíz tiene menos de 4
      letras, la fuente busca solo las variantes escritas: el alcance
      depende de que estén completas. Puede sugerir candidatas, pero cada
      una la confirma el investigador;
    - en una enmienda, escribe las secciones, muestra el diff con
      `enmendar --simular` y prepara `enmienda.json` y las justificaciones
      de las advertencias nuevas.

### Escritura del protocolo por secciones

13. **`agentresearch protocolo escribir <sección> --archivo fragmento.yaml [--protocolo ruta] [--json]`**
    es la única vía para escribir el protocolo desde Claude Code, porque los
    permisos niegan editar `protocolo/` (punto 15).
    - El fragmento tiene una sola clave de primer nivel, la sección, con su
      contenido completo: lo que no está en él se elimina.
    - Valida el protocolo completo contra el esquema **antes** de escribir y
      comprueba que el texto nuevo se lee como el modelo validado.
    - Escribe con la fusión del ADR-0006, así que lo que no cambia conserva
      comentarios y estilo, y lo nuevo conserva las comillas del fragmento.
      La escritura es atómica.
    - Se niega si el archivo cambió mientras tanto, si hay P-E00 (el
      investigador corrige a mano), si hay P-E10 o si hay una operación
      interrumpida que recuperar. No escribe `version_esquema`, `estado` ni
      `metadatos.version_protocolo`.
    - **Funciona también con el protocolo vigente:** es la forma de
      preparar una enmienda. Después de escribir, P-E09 avisa del cambio sin
      registrar hasta que el investigador registra la enmienda.
    - Muestra la validación del resultado y sale con 0 aunque el borrador,
      incompleto, tenga errores de contenido.
14. **Comentarios de sección de primer nivel** (límite del ADR-0006).
    - Al leer, el documento guarda las líneas de comentario que preceden a
      cada clave de primer nivel. Al escribir, las quita de donde las dejó
      ruamel.yaml y las pone antes de su clave. Los demás comentarios no se
      tocan.
    - Las pruebas cubren vaciar una lista, vaciar una lista anidada, agregar
      un elemento al final de una sección y conservar las notas del
      investigador sobre una sección.
    - **Fuente de los comentarios:** los del propio archivo. En un estudio,
      el protocolo nace de la plantilla, así que son los de la plantilla más
      las notas que agregue el investigador. Un archivo con el formato de la
      plantilla sale idéntico byte a byte, y uno sin comentarios de sección
      sigue sin ellos (ADR-0006, punto 12).

### Configuración de Claude Code en el estudio

15. **`.claude/settings.json`** fija el modelo con su identificador exacto,
    que `nuevo-estudio --modelo` exige con la misma regla que
    `propuesto_por.modelo` (ADR-0008, punto 16). El estudio de demostración
    usa `claude-opus-5-5`. Sus permisos:

    | Regla | Tipo | Efecto |
    |---|---|---|
    | `Bash(*agentresearch protocolo aprobar*)`, `Bash(*agentresearch protocolo decision confirmar*)` y sus equivalentes `PowerShell(…)` | `deny` | Claude no los ejecuta |
    | `Bash(*agentresearch protocolo enmendar*)` y `PowerShell(…)` | `ask` | pide permiso cada vez, también para `--simular` |
    | `Edit(/protocolo/**)`, `Edit(/estudio.yaml)`, `Edit(/CLAUDE.md)`, `Edit(/.claude/**)` | `deny` | Claude no edita el protocolo, el registro ni sus instrucciones |
    | `uv run agentresearch protocolo validar\|historial\|escribir\|ecuaciones\|decision registrar *`, `registro verificar *` (Bash y PowerShell); `Edit(/.borradores/**)` | `allow` | sin preguntar |

    `enmendar` va en `ask` y no en `deny` porque una regla `deny` gana
    siempre sobre una `allow`: negarlo bloquearía también `--simular`, que
    `/protocolo` necesita para mostrar el diff. La versión real igual se
    niega sin terminal.
16. **Sintaxis verificada** en la documentación de Claude Code
    (code.claude.com/docs/en/permissions, permission-modes y settings,
    consultadas el 2026-09-27):
    - `*` coincide con cualquier texto, también al inicio. Claude Code
      quita solo algunos envoltorios antes de comparar (`timeout`, `time`,
      `nice`, `nohup`, `stdbuf`, `command`, `builtin`, `xargs` sin opciones y
      algunas asignaciones de variables), y **`uv run` no es uno de ellos**.
      Por eso las reglas `deny` empiezan con `*`, y cubren `uv run …`,
      `python -m …` y la invocación directa;
    - las reglas `deny` y `ask` se aplican a cada subcomando de un comando
      compuesto. Las `deny` bloquean en todos los modos, incluido
      `bypassPermissions`, y las `ask` sobre un comando preguntan incluso en
      el modo automático;
    - las reglas de PowerShell tienen la misma forma que las de Bash;
    - las reglas `Edit(ruta)` se aplican a todas las herramientas
      integradas que editan archivos, incluida la escritura, y `/ruta` se
      ancla en el directorio del proyecto;
    - `.claude/` es una ruta protegida: su escritura nunca se aprueba sola
      fuera de `bypassPermissions`. La regla `deny` la vuelve firme;
    - las reglas `allow` de un proyecto solo se aplican después de aceptar
      el diálogo de confianza de la carpeta; las `deny` y `ask`, siempre;
    - `ANTHROPIC_MODEL` y `--model` tienen prioridad sobre la clave `model`.
      El `CLAUDE.md` del estudio pide no usarlos.
17. **Estas reglas no son una frontera de seguridad.** La documentación
    advierte que una regla sobre Bash cubre la forma en que Claude escribe
    el comando, no otras (por ejemplo `sh -c '…'`, o una ruta distinta al
    ejecutable). La barrera sigue siendo la confirmación interactiva del
    ADR-0008 (punto 11). Las reglas cortan la ruta habitual del LLM con un
    mensaje claro, y la terminal impide completarla por las demás.
18. **El aviso de «modelo en uso distinto del fijado» es de mejor
    esfuerzo.** `/protocolo` y el `CLAUDE.md` del estudio piden a Claude
    comparar su identificador exacto con el de `.claude/settings.json` y
    avisar antes de registrar nada. Depende de que el modelo conozca su
    propio identificador, y el paquete no puede comprobar qué modelo
    escribió una decisión (ADR-0008, punto 16). Lo que sí queda en el
    registro es el identificador que declara cada decisión y el modelo
    fijado en `estudio_creado`.

### Visibilidad

19. El repositorio de un estudio es **privado hasta registrar el
    protocolo** (p. ej. en OSF), y los pasos siguientes de `nuevo-estudio`
    lo crean así. El estudio de demostración es la excepción (punto 3).

## Aceptación

Pendiente: se completa con el resultado de la prueba del estudio de
demostración, en la terminal del investigador.

## Alternativas consideradas

- **Estrategia de validación:** aceptar el hito 1 con el caso piloto, como
  decía la especificación original. El protocolo de la tesis se construiría
  con una herramienta incompleta, y cada mejora posterior sería una
  enmienda.
- **`/protocolo` como comando** (`.claude/commands/protocolo.md`): funciona
  igual, pero sin archivos de apoyo toda la guía de secciones iría en un
  solo archivo y se cargaría entera cada vez.
- **Tema del estudio de demostración:**
  - hongos (*Pleurotus*) sobre pulpa o cascarilla de café (125 registros):
    más acotado, pero con una sola aplicación y menos facetas;
  - LLM en el cribado de revisiones sistemáticas (1084 registros): neutral,
    pero con demasiados registros, un tema que cambia muy rápido y
    circular con la propia herramienta.
- **Datos del estudio de demostración en `ejemplos/` de este repositorio:**
  cómodo para la integración continua, pero contradice la regla de un
  repositorio por estudio, crea una dependencia circular del agente
  consigo mismo y mezcla su `CLAUDE.md` y su `.claude/` con los de
  desarrollo.
- **Fijar el agente antes de `v0.1.0`:**
  - un commit exacto: no hace falta etiqueta, pero los eventos dirían
    `0.0.1`, que es engañoso;
  - una ruta local editable: no es reproducible, porque `uv.lock` guarda
    una ruta del equipo.
- **Barrera en los permisos:**
  - un gancho `PreToolUse` que revise el comando completo con una
    expresión regular: es más robusto, pero agrega un guion y un proceso en
    cada llamada;
  - negar también `enmendar`: bloquearía `--simular`.
- **Que Claude edite el YAML con sus herramientas de archivos:** es más
  simple, pero una edición mal hecha rompe el YAML, no se valida antes de
  escribir y no cumple «nada entra al estudio sin un comando del paquete».
- **Comentarios de sección siempre desde la plantilla:** reescribir un
  archivo sin comentarios los agregaría y rompería la ida y vuelta idéntica
  del ADR-0006; y un protocolo creado con una versión anterior de la
  plantilla quedaría con el comentario viejo y el nuevo.
- **`nuevo-estudio` que ejecute `git init` y `uv sync`:** el paquete
  pasaría a depender de Git y de la red, y las pruebas de ambos.
- **Crear todas las carpetas de `arquitectura.md`:** necesitaría archivos
  vacíos para versionarlas y fijaría nombres antes de sus hitos.
- **Nota de instrucciones como advertencia P-A:** exigiría justificarla en
  cada aprobación o enmienda aunque el cambio fuera deliberado y ya
  conocido.

## Consecuencias

- Un estudio se crea con un comando, queda fijado a una versión exacta del
  agente y a un modelo exacto, y registra desde el primer evento con qué
  instrucciones trabajó el agente.
- Claude Code solo puede escribir el protocolo validando antes y a través
  del paquete. El investigador aprueba, enmienda y confirma en su terminal,
  con dos barreras de procedimiento: los permisos y la consola.
- Cada versión publicada del agente necesita su etiqueta `v<versión>`,
  porque `nuevo-estudio` la escribe en el estudio.
- Los estudios de demostración de los hitos siguientes se actualizan de
  versión con un commit visible en su repositorio.
- Queda pendiente, para un hito posterior, registrar una actualización
  deliberada de las instrucciones del agente.
- Si una versión futura de Claude Code cambia la sintaxis de permisos o de
  *skills*, hay que revisar las plantillas. Las pruebas de este repositorio
  fijan su contenido esperado.
