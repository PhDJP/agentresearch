# ADR-0006: Formato del protocolo y registro encadenado de eventos

- Estado: Propuesta
- Fecha: 2026-09-26
- Participantes: investigador doctoral y Claude Code

## Contexto

El hito 1 necesita dos piezas relacionadas, descritas en
[docs/especificaciones/hito_1_protocolo_y_trazabilidad.md](../especificaciones/hito_1_protocolo_y_trazabilidad.md):
un formato versionado para el protocolo del estudio (sub-hito 1b) y un
mecanismo para dejar trazado cada evento de su ciclo de vida (sub-hito 1a).
El ADR-0004 ya fija la política general de trazabilidad (qué se registra y
por qué); este ADR fija el formato técnico concreto.

Este documento se completa en dos partes, una por sub-hito. La sección del
registro encadenado (1a) ya está decidida e implementada; la sección del
formato del protocolo (1b) se redacta al implementar ese sub-hito, y el
estado pasa a "Aceptada" cuando ambas estén completas.

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
    reportes que se publiquen.

### Formato del protocolo (sub-hito 1b)

Pendiente: se redacta al implementar el sub-hito 1b, con el esquema YAML
versionado (pydantic, versión de esquema 1) y las reglas de validación
P-E01 a P-E09 descritas en la especificación del hito 1.

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

## Consecuencias

- Cualquier cambio futuro en la lógica de serialización canónica invalidaría
  los hashes ya calculados en registros existentes; por eso el formato
  descrito aquí se considera estable a partir de este ADR, y un cambio
  incompatible requeriría un ADR nuevo que lo reemplace, no una edición de
  este.
- La verificación es local, rápida y no depende de red ni de un tercero de
  confianza, lo que permite ejecutarla en la integración continua y antes de
  cada enmienda del protocolo (sub-hito 1c).
- Queda pendiente decidir, en el sub-hito 1c, qué eventos concretos se
  registran en el ciclo de vida del protocolo (`protocolo_aprobado`,
  `protocolo_enmendado`, decisiones O1–O10) y cómo referencian el hash del
  archivo del protocolo en el momento de cada evento.
- El sub-hito 1c no se da por completo, en lo que toca a trazabilidad, hasta
  implementar el anclaje descrito en el punto 10: sin él, la cadena por sí
  sola no respalda una afirmación de "estos son todos los eventos", solo
  "estos eventos, en este orden, no fueron alterados".
