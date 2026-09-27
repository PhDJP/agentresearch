# Especificación del hito 1: protocolo y trazabilidad

- **Estado:** propuesta del asesor (2026-09-25). Se revisa con el investigador antes de implementar cada sub-hito.
- **Relación con otros documentos:** complementa la [hoja de ruta](../hoja_de_ruta.md), los [ADR](../decisiones/README.md) y las [reglas metodológicas](../metodologia/reglas_metodologicas.md). Si algo aquí contradice un ADR aceptado, prevalece el ADR y se corrige este documento.

## Objetivo

Al terminar el hito 1, un investigador puede:

1. crear el repositorio de un estudio;
2. construir su protocolo con la guía de Claude Code;
3. validarlo contra reglas metodológicas;
4. aprobarlo;
5. dejar trazada cada decisión y cada enmienda.

La prueba de aceptación es un estudio de demostración: un tema real y neutral, distinto del caso piloto. El caso piloto (subproductos del CBD) se ejecuta en el hito 11, con el agente terminado (decisión del 2026-09-27; ver «Estrategia de validación» en la hoja de ruta).

## Sub-hitos

Cada sub-hito se trabaja en una sesión de Claude Code, con plan aprobado antes de programar. Termina con pruebas en verde y un resumen para revisión del asesor.

| Sub-hito | Contenido | Esfuerzo sugerido en Claude Code |
|---|---|---|
| 1a | Trazabilidad: registro encadenado y hashes | Medio |
| 1b | Modelo del protocolo, YAML y validación | Alto |
| 1c | Ciclo de vida: aprobación, enmiendas y decisiones del protocolo | Alto |
| 1d | Ecuaciones de búsqueda por fuente | Alto |
| 1e | Repositorio de estudio, plantilla y comando `/protocolo`; aceptación con el estudio de demostración | Alto |

Al cerrar 1e se etiqueta `v0.1.0`.

Pendientes menores del hito 0, para incluir en el primer commit de 1a:

- agregar `repository-code` a `CITATION.cff`;
- actualizar las acciones de GitHub a versiones compatibles con el nuevo entorno de Node.js, si ya existen.

Origen de algunos ajustes: una auditoría de solo lectura hecha con GitHub Copilot (2026-09-25) coincidió con el orden de los sub-hitos y sugirió probar `main()`, exigir la cobertura en la integración continua y separar en el README lo disponible de lo diseñado.

## 1a. Trazabilidad

**Módulo `agentresearch.trazabilidad`.**

### Registro encadenado

Clase `RegistroEncadenado(ruta)`, un archivo JSONL al que solo se añaden líneas.

- **`agregar(tipo, datos)`** añade una línea en JSON canónico: claves ordenadas, UTF-8 sin escapar, sin espacios sobrantes, fin de línea LF. Cada línea tiene estos campos:

  | Campo | Contenido |
  |---|---|
  | `id` | Secuencial por archivo: `evt-000001`, `evt-000002`, … |
  | `tipo` | Por ejemplo `protocolo_aprobado` |
  | `fecha_hora_utc` | ISO 8601 con `Z` |
  | `version_agente` | Versión del paquete |
  | `datos` | Objeto con el contenido del evento |
  | `hash_anterior` | Hash de la línea anterior; la primera usa el valor fijo `sha256:genesis` |
  | `hash` | SHA-256 de la línea serializada sin el campo `hash` |

- **`leer()`** devuelve los eventos tipados.
- **`verificar()`** detecta líneas modificadas, eliminadas, insertadas o reordenadas, y reporta en qué línea se rompe la cadena.
- Nunca reescribe el archivo: abre en modo de adición y no edita líneas existentes.

La cadena no es una firma criptográfica, porque cualquiera podría recalcularla. Su valor como evidencia viene de combinarla con el historial de Git y el depósito en Zenodo. Así debe declararse.

### Utilidades

- `hash_archivo(ruta)` y `hash_texto(texto)`, con formato `sha256:<hex>`. Los archivos se leen en binario; `.gitattributes` garantiza LF, por lo que el hash coincide entre Windows y Linux.
- Reloj inyectable (función que devuelve la hora UTC) para que las pruebas sean deterministas.

### CLI y pruebas

- **CLI:** `agentresearch registro verificar <archivo.jsonl>`. Sale con código 0 si la cadena es íntegra y 1 si no.
- **Pruebas:**
  - una cadena válida se verifica;
  - se detectan un carácter alterado, una línea eliminada, líneas reordenadas y una línea insertada;
  - la serialización es idéntica en ejecuciones repetidas;
  - la fecha y hora siempre están en UTC;
  - la función `main()` y el punto de entrada instalado (ejecutando `uv run agentresearch --version` y `uv run agentresearch registro verificar` como subproceso), incluidos los argumentos inválidos.

## 1b. Modelo del protocolo

**Dependencias nuevas:** pydantic (MIT) y ruamel.yaml (MIT), que conserva los comentarios del YAML. La CLI sigue con argparse; si se quiere cambiar a typer, se justifica en un ADR.

### Estructura de `protocolo/protocolo.yaml` (versión de esquema 1)

Claves en español sin tildes. Abreviado:

```yaml
version_esquema: 1
estado: borrador                # borrador | vigente
metadatos:
  titulo: ""
  version_protocolo: "0.1.0"    # versionado semántico del protocolo
  autores: [{nombre: "", orcid: "", rol: ""}]
  registro: {plataforma: "", identificador: "", url: ""}   # PRISMA-ScR 5 (opcional)
  financiacion: ""                                        # PRISMA-ScR 22
justificacion: ""               # PRISMA-ScR 3
objetivos: ""
pregunta_general: ""
preguntas:                      # PRISMA-ScR 4
  - {id: PI1, texto: "", tipo: descriptiva, responde_con: [DE1, F1]}
  - {id: PI5, texto: "", tipo: analitica, derivada_de: [[F1, F2]]}
marco:
  pcc:
    poblacion: {descripcion: "", terminos: []}
    concepto:  {descripcion: "", terminos: []}
    contexto:  {descripcion: "", terminos: [], restrictivo: false}
  equivalencia_picoc: {population: "", intervention: "", comparison: "", outcome: "", context: ""}
fuentes:                        # PRISMA-ScR 7
  - {id: openalex, tipo: api, cobertura: "", limites: ""}
  - {id: scopus, tipo: exportacion, cobertura: "", limites: ""}
estrategias:
  bases_de_datos: {activa: true}
  bola_de_nieve: {activa: true, direcciones: [atras, adelante]}
  busqueda_manual: {activa: false, fuentes: []}
  conjunto_validacion: {activo: true, articulos: [{doi: "", titulo: "", como_se_conoce: ""}]}
  criterio_parada: {tipo: umbral_nuevos, valor: 0, justificacion: ""}
busqueda:                       # PRISMA-ScR 8
  bloques:                      # AND entre bloques, OR dentro de cada bloque
    - {id: B1, nombre: "", componente: poblacion, terminos: []}   # poblacion | concepto | contexto | otro
  periodo: {desde: null, hasta: null, justificacion: ""}
  idiomas: {valores: [], justificacion: ""}
  tipos_documento: []
criterios:                      # PRISMA-ScR 6
  inclusion: [{id: CI1, texto: "", fase: titulo_resumen, tipo: tema, ejemplos_si: [], ejemplos_no: []}]
  # tipo: tema | lugar_publicacion | periodo | evaluacion_empirica | idioma | tipo_documento | otro
  exclusion: [{id: CE1, texto: "", fase: ambas, tipo: tema, ejemplos_si: [], ejemplos_no: []}]
seleccion:                      # PRISMA-ScR 9
  revisores: [{id: investigador-1, tipo: humano}, {id: claude, tipo: llm}]
  regla_combinacion: {avanzan: [A, B, C, D, E]}
  piloto: {tamano: 0, umbral_kappa: 0.61}
  tamano_lote_llm: 25
extraccion:                     # PRISMA-ScR 10 y 11
  items: [{id: DE1, nombre: "", descripcion: "", tipo: categoria, categorias: [], preguntas: [PI1]}]
  facetas:
    - {id: F1, nombre: "", origen: emergente, multiple: true,
       categorias: [{id: F1.1, nombre: "", definicion: "", regla: "", ejemplos: []}]}
calidad: {activa: false, preguntas: []}   # PRISMA-ScR 12 (opcional)
analisis: {plan: "", cruces: [[F1, F2]]}  # PRISMA-ScR 13
```

La plantilla del paquete lleva, en cada sección, un comentario de una línea que explica para qué sirve y qué guía la exige.

### Validaciones

Cada regla tiene un ID estable, que aparece en los mensajes y en las pruebas.

**Errores** (impiden aprobar):

| ID | Regla |
|---|---|
| P-E00 | El archivo es legible, es YAML válido y cumple el esquema (en YAML mal formado, con línea y columna). Si falla, no se evalúan las demás reglas |
| P-E01 | IDs únicos y con el patrón de su tipo: `PI`, `CI`, `CE`, `DE`, `F`, `B` seguidos de un número |
| P-E02 | Toda referencia (`responde_con`, `derivada_de`, `preguntas`, `cruces`) apunta a un ID existente |
| P-E03 | Cada pregunta descriptiva tiene al menos un dato que la responde; cada pregunta analítica declara de qué cruces se deriva |
| P-E04 | Población y concepto no están vacíos; hay al menos un bloque de búsqueda y cada bloque tiene al menos un término |
| P-E05 | Cada criterio declara su fase |
| P-E06 | `regla_combinacion.avanzan` contiene A y no contiene F |
| P-E07 | Hay al menos un revisor humano (regla 1 de CLAUDE.md) |
| P-E08 | `umbral_kappa` está entre 0 y 1; el tamaño del lote es un entero positivo |

**Advertencias metodológicas** (se muestran con su referencia y no impiden aprobar, pero el investigador debe revisarlas):

| ID | Advertencia | Referencia |
|---|---|---|
| P-A01 | Criterio de inclusión que exige evaluación empírica | Petersen et al. (2015), §5.1.2 |
| P-A02 | Contexto marcado como restrictivo, o usado como bloque AND de búsqueda | Petersen et al. (2015), §5.1.2 |
| P-A03 | Solo una estrategia de identificación activa | Petersen et al. (2015), tabla 10 |
| P-A04 | Conjunto de validación inactivo o con menos de 5 artículos | Petersen et al. (2015), §5.1.2 |
| P-A05 | Periodo o idioma restringido sin justificación | PRISMA-ScR, ítem 6 |
| P-A06 | Categoría de faceta sin definición, regla o ejemplos | Wohlin et al. (2013) |
| P-A07 | Acrónimo corto (4 letras o menos, en mayúsculas) suelto en un bloque, con riesgo de colisión (p. ej. "CBD") | Lección del ejercicio previo del caso piloto |
| P-A08 | Sin un segundo revisor humano para el piloto de cribado | Petersen et al. (2015), §5.1.2 |

Ajustes aprobados al implementar 1b (2026-09-26); el detalle está en el [ADR-0006](../decisiones/0006-formato-del-protocolo-y-registro-encadenado.md):

- **Esquema.** El tipo de criterio es una enumeración (tipos a–e de Petersen et al., 2015, §5.1.2, más `tipo_documento` y `otro`). Cada bloque declara su componente PCC. `idiomas` tiene la forma `{valores, justificacion}`, y el periodo se expresa en años. Cada cruce tiene al menos dos IDs, y `version_protocolo` sigue la forma `X.Y.Z`.
- **Referencias de los errores.** P-E01: CLAUDE.md, regla 2. P-E02: reglas metodológicas, §2. P-E03: Petersen et al. (2015), tabla 3. P-E04: PRISMA-ScR, ítems 4 y 8; Peters et al. (2024), JBI. P-E05: PRISMA-ScR, ítem 6. P-E06: Petersen et al. (2015), tabla 6. P-E07: CLAUDE.md, regla 1; declaración conjunta Cochrane, Campbell, JBI y CEE (2025). P-E08: Landis y Koch (1977).
- **Precisiones de las advertencias.** P-A01 también salta con criterios de exclusión de tipo `evaluacion_empirica`. P-A02 detecta el contexto restrictivo, los bloques de componente `contexto` y los términos de contexto repetidos en otro bloque. P-A07 salta con o sin comillas. P-A08 salta con un solo revisor humano; sin ninguno, ya salta P-E07.
- **Salida `--json`.** Incluye la versión del agente y el hash del archivo.

### CLI y pruebas

- **CLI:** `agentresearch protocolo validar [ruta] [--json]`. Sale con código 1 si hay errores y 0 si solo hay advertencias. La salida en JSON sirve para que Claude Code la interprete.
- **Pruebas:**
  - un protocolo sintético válido, con un tema ficticio distinto del caso piloto;
  - un caso que dispare cada error y cada advertencia;
  - lectura y escritura del YAML conservando comentarios;
  - mensajes con ID de regla y referencia.

## 1c. Ciclo de vida del protocolo

Las decisiones de este sub-hito (estados, eventos que se registran, P-E09 y anclaje del registro) se documentan en el ADR-0008, no en el ADR-0006, que quedó aceptado al cerrar 1b.

**Estados:** `borrador` → `vigente`. Los eventos se registran en `protocolo/eventos.jsonl` con el registro encadenado de 1a.

- **`agentresearch protocolo aprobar`**
  - exige cero errores y la confirmación explícita del investigador (`--confirmo`);
  - pasa el estado a `vigente`;
  - registra `protocolo_aprobado` con la versión y el hash del archivo.
- **`agentresearch protocolo enmendar --justificacion "…" --efecto-esperado "…" [--nivel menor|mayor]`**
  - exige que el archivo haya cambiado desde el último hash registrado;
  - incrementa la versión del protocolo;
  - registra `protocolo_enmendado` con el hash anterior, el hash nuevo y un diff estructural campo por campo, generado por el paquete y no por el LLM.
- **Cambios sin registrar.** Si el protocolo está `vigente` y su hash no coincide con el último registrado, `validar` da el error **P-E09** ("cambio sin enmienda registrada").
- **`agentresearch protocolo decision registrar --archivo decision.json`** registra una decisión del protocolo, como O1 a O10 del caso piloto. Esquema:
  ```json
  {
    "id_decision": "O1",
    "tema": "Límites de la población",
    "pregunta": "¿Qué cuenta como subproducto?",
    "opciones": [
      {"id": "A", "descripcion": "…", "pros": ["…"], "contras": ["…"], "referencias": ["…"]}
    ],
    "elegida": "A",
    "justificacion": "…",
    "propuesto_por": {"tipo": "llm", "modelo": "<identificador exacto>"},
    "decidido_por": {"tipo": "humano", "id": "investigador-1"}
  }
  ```
  Se validan:
  - que haya entre 2 y 4 opciones;
  - que `elegida` exista entre ellas;
  - que `decidido_por.tipo` sea `humano`.
- **`agentresearch protocolo historial`** lista versiones, enmiendas y decisiones. Alimenta los ítems 5 (protocolo) y 20 (desviaciones) de PRISMA-ScR.
- **Anclaje del registro** (punto 10 del ADR-0006): `protocolo historial` y los reportes muestran el número de eventos y el hash del último, para detectar la eliminación de eventos finales.
- **Pruebas:** aprobar con errores falla; editar un protocolo vigente sin enmienda produce P-E09; una enmienda incrementa la versión y registra el diff; una decisión tomada por un LLM se rechaza.

Ajustes aprobados al implementar 1c (2026-09-26); el detalle está en el [ADR-0008](../decisiones/0008-ciclo-de-vida-del-protocolo.md):

- **Confirmación.** `--confirmo` se reemplaza por `--aprobado-por` y `--enmendado-por`, que deben ser revisores humanos declarados, y por una confirmación interactiva que exige una consola. Es una barrera de procedimiento, no una garantía.
- **Versiones.** Aprobar fija `1.0.0`. `--nivel mayor|menor` es obligatorio al enmendar, y el paquete asigna el parche cuando el diff estructural sale vacío. El contenido anterior del diff sale de copias exactas de cada versión en `protocolo/versiones/`.
- **Atomicidad.** Se escriben, en este orden, la copia, el evento, el anclaje y el protocolo, con `fsync`. Una operación interrumpida se reconoce y se recupera con la copia.
- **Decisiones en dos pasos.** `decision registrar` deja la decisión como propuesta, y `decision confirmar` la confirma en la terminal. `aprobar` y `enmendar` se niegan si hay decisiones pendientes. Se exigen además pros, contras y referencias en cada opción, un revisor humano declarado y el identificador exacto del modelo.
- **Advertencias.** Aprobar exige una justificación por cada advertencia activa.
- **Reglas nuevas.** P-E10 (registro íntegro y conforme a su anclaje) y P-A09 (piloto sin tamaño). P-E09 mira el registro y no solo el campo `estado`. P-E09 y P-E10 leen el directorio del estudio.
- **Anclaje.** Tiene la forma `evt-NNNNNN@sha256:<hex>`, se verifica como prefijo y se guarda en `protocolo/anclaje.json`. Además lo muestran `historial`, `validar` y `registro verificar --anclaje`.

## 1d. Ecuaciones de búsqueda por fuente

- **Entrada:** los bloques del protocolo (AND entre bloques, OR dentro de cada uno). Cada término es una palabra, una frase (entre comillas) o un truncamiento (`*`).
- **Salida:** una ecuación por fuente (OpenAlex, PubMed, Scopus, Web of Science y una genérica), guardada en `protocolo/ecuaciones.md` con la versión y el hash del protocolo de origen.
- **Sintaxis.** Cada traductor documenta en su código la URL de la documentación oficial y la fecha en que se verificó. La sintaxis se verifica contra esa documentación al implementar, no con lo que el modelo recuerda.
- **Funciones no soportadas.** Si una fuente no admite algo (p. ej. truncamiento), el traductor lo informa y aplica una alternativa explícita, como expandir variantes. Nunca lo omite en silencio.
- **Límites de longitud.** Se advierte cuando una ecuación supera el máximo conocido de la fuente.
- **Pruebas:** archivos de referencia (*golden files*) por fuente, a partir de bloques sintéticos.

Ajustes aprobados al implementar 1d (2026-09-26 y 2026-09-27); el detalle está en el [ADR-0009](../decisiones/0009-ecuaciones-de-busqueda-por-fuente.md):

- **Términos.** Un término es una palabra (con guiones, apóstrofos o tildes), una palabra truncada o una frase entre comillas. Lo que no se traduce igual en todas las fuentes es el error nuevo **P-E11**: por ejemplo, varias palabras sin comillas, operadores, sintaxis de campo o comodines distintos de `*` final.
- **Variantes.** Cada bloque admite `variantes: {término truncado: [variantes]}`, un campo opcional que no cambia la versión del esquema. Un traductor las usa donde la fuente no admite el truncamiento; sin ellas, esa fuente queda bloqueada con un aviso. El paquete nunca las inventa.
- **Fuentes.** Se traducen las fuentes declaradas con ID `openalex`, `pubmed`, `scopus` o `wos`, más la genérica.
- **Lo no documentado se trata como no admitido.** Por ejemplo, el truncamiento dentro de frases en Web of Science.
- **OpenAlex.** Busca en título y resumen con `title_and_abstract.search`, verificado con consultas reales a la API (2026-09-27). Los términos con guion van entre comillas. Cada bloque es un filtro con su propio modo: conserva la búsqueda lematizada si sus truncados tienen variantes y ninguna frase ni término con guion contiene palabras vacías; si no, ese bloque usa `search.exact` y se avisa.
- **Guiones en Scopus.** Van entre comillas, porque Elsevier solo documenta el guion dentro de una frase aproximada.
- **Límites.** Scopus y Web of Science, que se usan por exportación manual, traducen los límites verificados y dan instrucciones de interfaz para el resto. OpenAlex y PubMed los dejan para los conectores del hito 3.
- **Comando.** `agentresearch protocolo ecuaciones [ruta] [--escribir] [--json]`. No registra un evento. Con `--escribir` se niega también con P-E09. Si hay fuentes bloqueadas, escribe igual y sale con 1.
- **`ecuaciones.md`.** Es determinista. Para Scopus y Web of Science incluye los pasos del investigador: dónde pegar la ecuación, los filtros, el formato de exportación y qué anotar.
- **Ecuaciones desactualizadas.** Se avisan con una nota de estado en `validar` e `historial`, no con una advertencia P-A: una advertencia exigiría justificarla en cada enmienda.

## 1e. Repositorio de estudio y comando `/protocolo`

### `agentresearch nuevo-estudio <ruta> --titulo "…" [--contexto archivo.md]`

Crea la estructura de carpetas de [arquitectura.md](../arquitectura.md) con:

- `estudio.yaml`: nombre, versión exacta del agente, fecha y licencia de datos CC BY 4.0;
- `protocolo/protocolo.yaml` desde la plantilla;
- `protocolo/eventos.jsonl` con su evento inicial;
- el `CLAUDE.md` del estudio y los comandos de Claude Code;
- un `.gitignore` del estudio (PDF de texto completo, `.env`, material con derechos);
- un `README.md`.

Si se da `--contexto`, lo copia como insumo en `protocolo/insumos/`.

### Instalación reproducible del agente en el estudio

El repositorio del estudio es un proyecto uv que depende del agente fijado a una etiqueta, por ejemplo `agentresearch @ git+https://github.com/PhDJP/agentresearch@v0.1.0`, y su `uv.lock` se versiona.

### `CLAUDE.md` del estudio (plantilla)

- Reglas de comportamiento (sección "Comportamiento del agente en un estudio" de `arquitectura.md`).
- Lista de comandos disponibles.
- Instrucción de fijar el modelo con su identificador completo en `.claude/settings.json` del estudio.

### Comando `/protocolo`

Se implementa como comando o *skill* de Claude Code, según lo que la versión actual de Claude Code documente como recomendado; la decisión se registra en el ADR-0007. Su flujo:

1. Leer `protocolo.yaml`, el historial y los insumos (p. ej. el contexto del caso piloto).
2. Recorrer las secciones en orden: justificación, preguntas, PCC y equivalencia PICOC, fuentes, estrategias, búsqueda, criterios, selección, extracción y facetas, calidad y análisis.
3. En cada sección, explicar en una o dos frases para qué sirve y qué guía lo exige, y preguntar una cosa a la vez.
4. Si el investigador no sabe qué responder, proponer de 2 a 4 opciones fundamentadas y registrar la elección con `protocolo decision registrar`.
5. Al cerrar cada sección, escribir en `protocolo.yaml`, ejecutar `protocolo validar` y mostrar las advertencias con una propuesta para resolverlas.
6. Al final, mostrar un resumen completo y pedir aprobación explícita. Nunca aprobar sin ella.

Ajustes aprobados al implementar 1e (2026-09-27); el detalle está en el [ADR-0007](../decisiones/0007-repositorio-de-estudio.md):

- **`/protocolo` es una *skill*** con `disable-model-invocation: true` y dos archivos de apoyo (guía por sección y formatos), como recomienda la documentación actual de Claude Code.
- **`nuevo-estudio --modelo ID`** es obligatorio y exige un identificador exacto. Solo crea `protocolo/`; las carpetas de las demás fases las crea cada hito. No ejecuta Git ni uv: muestra los pasos siguientes. El estudio es un proyecto uv que fija el agente a la etiqueta `v<versión>`.
- **Evento inicial `estudio_creado`,** con el hash de cada archivo creado, de las instrucciones del agente (`CLAUDE.md`, `.claude/settings.json` y la *skill*) y de los insumos. `validar` e `historial` muestran la nota «instrucciones del agente modificadas» si esos archivos cambian.
- **`protocolo escribir <sección> --archivo fragmento.yaml`** es la vía para escribir el protocolo: valida contra el esquema antes de escribir y conserva comentarios y estilo. Funciona también con el protocolo vigente, para preparar una enmienda.
- **Comentarios de sección:** la escritura restaura los del propio archivo, que en un estudio nace de la plantilla.
- **Permisos del estudio:** se niegan `aprobar` y `decision confirmar`, `enmendar` pregunta cada vez (para permitir `--simular`), y se niega editar `protocolo/`, `estudio.yaml`, `CLAUDE.md` y `.claude/`. No son una frontera de seguridad: la barrera sigue siendo la terminal.
- **Versión del agente:** antes de `v0.1.0`, el estudio de demostración se fija a la etiqueta candidata `v0.1.0rc1`.

### Aceptación con el estudio de demostración

- El ADR-0007 fija el tema del estudio de demostración (real y neutral, distinto del caso piloto, de pocos registros) y dónde viven sus datos.
- Se crea su repositorio con `nuevo-estudio`.
- `/protocolo` construye el protocolo de punta a punta, incluidas al menos dos decisiones registradas con `decision registrar` y confirmadas por el investigador en su terminal.
- `validar` da cero errores y todas las advertencias quedan justificadas.
- El investigador aprueba el protocolo como `1.0.0` en su propia terminal (PowerShell o la terminal de VS Code), se generan las ecuaciones con `ecuaciones --escribir`, y `historial` muestra todo el recorrido con su anclaje.

El protocolo del caso piloto se construye con este mismo flujo en el hito 11.

## ADR que el hito 1 debe producir

- **ADR-0006:** formato del protocolo (YAML, esquema pydantic y versión de esquema) y registro encadenado de eventos. Aceptado al cerrar 1b.
- **ADR-0007:** repositorio de estudio. Cubre su estructura, la instalación del agente fijada a una etiqueta, comando o *skill* de Claude Code, y la visibilidad privada hasta registrar el protocolo.
- **ADR-0008:** ciclo de vida del protocolo. Cubre los estados, la aprobación, las enmiendas y su diff estructural, los eventos que se registran, las decisiones del protocolo, la regla P-E09 y el anclaje del registro encadenado.

## Criterio de terminado del hito 1

- Sub-hitos 1a a 1e completos, con pruebas.
- Cobertura de al menos 90 % en `trazabilidad` y `protocolo`, verificada por la integración continua:
  ```powershell
  uv run coverage report --include="src/agentresearch/trazabilidad/*,src/agentresearch/protocolo/*" --fail-under=90
  ```
- CI en verde en Windows y Ubuntu.
- ADR 0006, 0007 y 0008, y `CHANGELOG.md` actualizado.
- Etiqueta `v0.1.0`.
- Protocolo del estudio de demostración aprobado.
