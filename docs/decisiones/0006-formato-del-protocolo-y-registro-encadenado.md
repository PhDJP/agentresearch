# ADR-0006: Formato del protocolo y registro encadenado de eventos

- Estado: Aceptada
- Fecha: 2026-09-26
- Participantes: investigador doctoral y Claude Code

## Contexto

El hito 1 necesita dos piezas relacionadas, descritas en
[docs/especificaciones/hito_1_protocolo_y_trazabilidad.md](../especificaciones/hito_1_protocolo_y_trazabilidad.md):
un formato versionado para el protocolo del estudio (sub-hito 1b) y un
mecanismo para dejar trazado cada evento de su ciclo de vida (sub-hito 1a).
El ADR-0004 ya fija la política general de trazabilidad (qué se registra y
por qué); este ADR fija el formato técnico concreto.

Este documento se redactó en dos partes, una por sub-hito: el registro
encadenado (1a) y el formato del protocolo (1b). Ambas están implementadas
y el ADR queda aceptado. El ciclo de vida del protocolo (sub-hito 1c:
aprobación, enmiendas, eventos que se registran, la regla P-E09 y el
anclaje del registro descrito en el punto 10) se decide en un ADR nuevo, el
ADR-0008, y no en este.

## Decisión

### Registro encadenado de eventos (sub-hito 1a)

1. **Formato de archivo.** JSONL (una línea, un evento) de solo adición.
   `RegistroEncadenado` nunca reescribe ni elimina líneas existentes; solo
   abre el archivo en modo de adición.
2. **Cada línea es un objeto JSON canónico**, para que el hash sea
   reproducible entre ejecuciones y sistemas operativos: claves ordenadas
   (`sort_keys=True`), sin escapar caracteres no ASCII (`ensure_ascii=False`),
   sin espacios sobrantes (`separators=(",", ":")`) y sin valores no finitos
   (`allow_nan=False`). El archivo se escribe con codificación UTF-8 y fin de
   línea LF explícito (`newline="\n"`), para que el hash coincida entre
   Windows y Linux pese a `.gitattributes`.
3. **Campos de cada evento:** `id` secuencial (`evt-000001`, `evt-000002`,
   …), `tipo`, `fecha_hora_utc`, `version_agente`, `datos`, `hash_anterior` y
   `hash`.
4. **Fecha y hora.** ISO 8601 en UTC, con `Z` y precisión fija en
   milisegundos (por ejemplo `2026-09-26T12:00:00.000Z`), para que el campo
   tenga siempre el mismo largo y la serialización sea determinista. Se exige
   que la fecha tenga zona horaria; una fecha ingenua (sin zona) se rechaza
   con un error explícito, tanto al formatear como al usar el reloj
   inyectado.
5. **Reloj inyectable.** `RegistroEncadenado` recibe una función sin
   argumentos que devuelve la fecha y hora actual (por defecto,
   `datetime.now(UTC)`), para que las pruebas sean deterministas sin
   necesidad de simular el paso del tiempo real.
6. **Encadenamiento.** `hash_anterior` de un evento es exactamente el valor
   del campo `hash` del evento anterior (`sha256:genesis` en el primero, un
   valor fijo y reconocible). `hash` es el SHA-256, con prefijo `sha256:`, de
   la serialización canónica del evento sin el campo `hash`.
7. **Verificación.** `verificar()` no confía en los valores declarados: relee
   el archivo línea por línea y valida, en orden, la secuencia de `id`, la
   coincidencia de `hash_anterior` con el hash real del evento previo, que la
   línea (sin su retorno de carro final, por si el archivo tuviera fin de
   línea CRLF) sea idéntica byte a byte a la serialización canónica del
   objeto que declara, y la coincidencia del `hash` declarado con el
   recalculado a partir del resto de los campos. La comparación byte a byte
   contra la forma canónica es necesaria porque el hash por sí solo no
   detecta un reformateo del archivo (por ejemplo, reordenar las claves de un
   evento) que no cambie los valores de sus campos. Reporta la primera línea
   donde la cadena se rompe, junto con una razón legible, ya sea por una
   línea alterada, eliminada, insertada, reordenada, con JSON inválido, o
   truncada (por ejemplo, por un proceso interrumpido a mitad de escritura).
   Un archivo inexistente es un error de `verificar()`, no una cadena vacía
   válida.
8. **Escritura defensiva.** `agregar()` verifica la cadena existente antes de
   escribir, y se niega con un error explícito si está rota o si el archivo
   no termina en un salto de línea (señal de una escritura anterior
   incompleta). Así, el registro nunca construye un evento nuevo sobre una
   base ya comprometida.
9. **Alcance como evidencia.** La cadena de hashes no es una firma
   criptográfica: cualquiera con acceso de escritura al archivo podría
   recalcularla por completo. Su valor como evidencia viene de combinarla con
   el historial de Git (que registra cuándo cambió el archivo) y el depósito
   del repositorio del estudio en Zenodo con DOI. Los reportes del estudio
   deben declarar esta limitación explícitamente, sin presentarla como una
   garantía criptográfica.
10. **Límite conocido: truncar el final no se detecta.** Si se eliminan las
    últimas *N* líneas del archivo, el prefijo restante sigue siendo, por sí
    mismo, una cadena perfectamente válida: ningún campo dentro del archivo
    declara cuántos eventos debería tener en total. `verificar()` no puede
    detectar, solo con el contenido del archivo, la eliminación de eventos al
    final del registro. La mitigación es un **anclaje** externo: guardar en
    otro lugar (el historial del protocolo, o un reporte depositado en
    Zenodo) el número de eventos esperado y el `hash` del último evento en un
    momento dado, para poder comparar el archivo actual contra ese anclaje y
    detectar así el truncamiento. Este anclaje no se implementa en 1a; queda
    a cargo del sub-hito 1c, en el comando `protocolo historial` y en los
    reportes que se publiquen, y su formato se decide en el ADR-0008.

### Formato del protocolo (sub-hito 1b)

11. **Archivo.** El protocolo de un estudio vive en
    `protocolo/protocolo.yaml`, en UTF-8 y con fin de línea LF. Se elige
    YAML porque admite comentarios (la plantilla explica cada sección al
    investigador), se lee sin herramientas y produce diferencias legibles
    en Git. La plantilla comentada está en el paquete
    (`agentresearch/protocolo/plantillas/protocolo.yaml`), y cada sección
    lleva un comentario de una línea con su propósito y la guía que la
    exige.
12. **Lectura y escritura con ruamel.yaml en modo de ida y vuelta.** Con
    indentación de 2 espacios en los mapas, guiones de lista con 2 espacios
    de sangría, un ancho de línea de 4096 (los párrafos no se parten),
    `preserve_quotes`, `null` explícito y claves duplicadas prohibidas.
    Leer y volver a escribir un protocolo sin cambios produce un archivo
    **idéntico byte a byte** si sigue el formato de la plantilla; si no lo
    sigue, la primera escritura lo normaliza. Esto importa porque el ciclo
    de vida del protocolo registra el hash del archivo.
13. **Escritura por fusión.** Para escribir, el modelo se fusiona sobre el
    YAML original, y no se regenera el archivo desde cero:
    - los mapas se fusionan clave por clave;
    - las listas cuyos elementos tienen `id` se fusionan por su `id`, no por
      posición, para que el comentario de un criterio siga a ese criterio
      aunque la lista se reordene;
    - las demás listas se fusionan por posición;
    - un texto que cambia conserva su estilo de comillas;
    - solo se escriben los campos presentes en el YAML o asignados
      explícitamente, no los valores por defecto implícitos del modelo.
14. **Esquema pydantic, versión 1** (`version_esquema: 1`), en
    `agentresearch.protocolo.modelo`, con `extra="forbid"` (una clave mal
    escrita no se ignora en silencio) y `strict=True` (sin conversiones
    implícitas: el texto `"25"` no es el entero 25). Respecto al esbozo de
    la especificación del hito 1, el esquema:
    - define el tipo de criterio como enumeración: los tipos (a) a (e) de
      Petersen et al. (2015, §5.1.2) (`tema`, `lugar_publicacion`,
      `periodo`, `evaluacion_empirica`, `idioma`), más `tipo_documento` y
      `otro`;
    - agrega a cada bloque de búsqueda su componente PCC (`poblacion`,
      `concepto`, `contexto` u `otro`);
    - da a `idiomas` la forma `{valores, justificacion}`, como el periodo;
    - expresa el periodo en años enteros (`null` es sin límite);
    - exige que cada cruce tenga al menos dos IDs y que
      `version_protocolo` siga el versionado semántico `X.Y.Z`.
15. **El esquema valida la forma y las reglas validan el contenido.** Un
    protocolo en borrador está incompleto por naturaleza. Por eso el
    esquema acepta textos vacíos, IDs con cualquier forma y la ausencia de
    los campos que vigila una regla (por ejemplo, la `fase` de un
    criterio), y las reglas de contenido reportan esas faltas con su propio
    ID.
16. **Versión del esquema.** El agente solo admite la versión 1; un archivo
    con otra versión es un error P-E00. Agregar un campo opcional no cambia
    la versión si los archivos existentes siguen siendo válidos. Renombrar
    o eliminar un campo, o cambiar su tipo, exige la versión 2, una
    migración explícita y un ADR nuevo.
17. **Reglas de validación** en `agentresearch.protocolo.reglas`, cada una
    con ID estable, severidad, descripción y referencia. Los errores (P-E)
    impiden aprobar; las advertencias (P-A) no, pero el investigador debe
    revisarlas. Un ID nunca se reutiliza para otra regla.
    - **P-E00** agrupa lo que impide cargar el protocolo: archivo inexistente
      o ilegible, codificación distinta de UTF-8, YAML mal formado (con
      línea y columna), clave duplicada, versión de esquema no soportada o
      incumplimiento del esquema (con la ubicación, la línea y la columna
      del campo). Si hay P-E00, no se evalúan las demás reglas.
    - **P-E01 a P-E08 y P-A01 a P-A08** son las de la especificación del
      hito 1, con las referencias del catálogo.
    - Precisiones: P-A01 salta con criterios de inclusión o de exclusión de
      tipo `evaluacion_empirica`. P-A02 salta con el contexto marcado como
      restrictivo, con un bloque de componente `contexto`, o con un término
      de contexto repetido en otro bloque. P-A03 cuenta como estrategias
      de identificación las bases de datos, la bola de nieve y la búsqueda
      manual, pero no el conjunto de validación. P-A04 cuenta solo
      artículos con DOI o título. P-A07 salta con un término de 2 a 4
      caracteres en mayúsculas con al menos dos letras, con o sin comillas
      y con o sin truncamiento. P-A08 salta con un solo revisor humano;
      sin ninguno, ya salta P-E07.
    - Las reglas son deterministas sobre el modelo y no interpretan el texto
      libre, salvo P-A07, que examina la forma de los términos.
    - P-E09 (cambio sin enmienda registrada) y las reglas del ciclo de vida
      se definen en el ADR-0008.
18. **Salida de `agentresearch protocolo validar [ruta] [--json]`.** Sale
    con código 1 si hay errores y 0 si solo hay advertencias. Cada hallazgo
    lleva ID de regla, severidad, mensaje, ubicación (por ejemplo
    `criterios.inclusion[0].fase`), línea, columna y referencia. La salida
    JSON incluye además la ruta, el hash del archivo, la versión del
    agente, la versión de esquema, y el estado y la versión del protocolo.
    Se emite en ASCII escapado para que sea JSON válido aunque la consola
    no use UTF-8.

## Alternativas consideradas

- **Firma criptográfica (GPG) de cada evento:** daría una garantía más
  fuerte que el encadenamiento por hash, pero exige que el investigador
  gestione una clave privada, lo que complica reproducir el estudio en un
  equipo nuevo. Se descarta para este registro; se reconsideraría en un ADR
  aparte si un revisor o una política institucional lo exige.
- **Base de datos (SQLite) para los eventos:** sería más cómoda para
  consultas complejas, pero CLAUDE.md exige texto plano versionable en Git
  para los datos del estudio, no binarios.
- **`hash_anterior` como hash de la línea anterior completa (en vez del
  campo `hash` de esa línea):** es equivalente en la práctica, porque `hash`
  ya es el hash de esa línea sin el campo `hash`. Se prefirió referenciar
  directamente el campo `hash` del evento anterior porque es más simple de
  calcular, de verificar y de explicar en el reporte del estudio.
- **Precisión de segundos en `fecha_hora_utc` (sin milisegundos):**
  suficiente para la mayoría de eventos, pero dos eventos automáticos
  seguidos (por ejemplo, generados por un mismo comando) podrían compartir el
  mismo segundo. Milisegundos reduce ese riesgo sin agregar complejidad.
- **PyYAML para el protocolo:** es más común, pero al reescribir el archivo
  pierde los comentarios, que son la guía del investigador en la plantilla.
- **TOML para el protocolo:** admite comentarios, pero las listas de mapas
  anidadas (criterios con ejemplos, facetas con categorías) resultan más
  verbosas y difíciles de leer que en YAML.
- **JSON Schema como fuente del esquema:** es independiente del lenguaje,
  pero duplicaría el modelo que el paquete ya necesita en Python, y
  CLAUDE.md fija pydantic para los esquemas de datos.
- **Validar el contenido con validadores de pydantic:** un borrador
  incompleto no cargaría, y las faltas saldrían como errores de esquema sin
  el ID de su regla metodológica.
- **Detectar P-A01 y P-A02 en el texto libre de los criterios:** sería
  heurístico y difícil de explicar. Se prefirió declarar el tipo de cada
  criterio y el componente de cada bloque, y validar esas declaraciones.
- **Regenerar el YAML desde el modelo al escribir:** es más simple, pero
  pierde los comentarios y el estilo del investigador.

## Consecuencias

- Cualquier cambio futuro en la lógica de serialización canónica invalidaría
  los hashes ya calculados en registros existentes; por eso el formato
  descrito aquí se considera estable a partir de este ADR, y un cambio
  incompatible requeriría un ADR nuevo que lo reemplace, no una edición de
  este.
- La verificación es local, rápida y no depende de red ni de un tercero de
  confianza, lo que permite ejecutarla en la integración continua y antes de
  cada enmienda del protocolo (sub-hito 1c).
- Queda pendiente decidir, en el ADR-0008 (sub-hito 1c), qué eventos
  concretos se registran en el ciclo de vida del protocolo
  (`protocolo_aprobado`, `protocolo_enmendado`, decisiones O1–O10) y cómo
  referencian el hash del archivo del protocolo en el momento de cada
  evento.
- El sub-hito 1c no se da por completo, en lo que toca a trazabilidad, hasta
  implementar el anclaje descrito en el punto 10: sin él, la cadena por sí
  sola no respalda una afirmación de "estos son todos los eventos", solo
  "estos eventos, en este orden, no fueron alterados".
- El protocolo se puede leer, editar a mano y validar sin el agente, y la
  validación es determinista, rápida y sin red, así que puede correr en la
  integración continua del repositorio de un estudio.
- Límite conocido de la escritura por fusión: ruamel.yaml guarda el
  comentario que precede a una clave como comentario posterior al nodo
  anterior. Si se elimina ese nodo (por ejemplo, el último criterio de una
  lista), el comentario de la sección siguiente puede perderse; y una clave
  nueva agregada al final de un mapa queda después de ese comentario. Las
  pruebas cubren los casos habituales (cambiar valores, agregar, reordenar
  y eliminar elementos con `id`) y verifican que los comentarios se
  conserven.
- `extra="forbid"` hace que un agente antiguo rechace un protocolo que use
  un campo opcional agregado en una versión posterior del agente. Esto es
  aceptable porque cada repositorio de estudio fija la versión exacta del
  agente (ADR-0005).
