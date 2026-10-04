# ADR-0010: Registros, importación de búsquedas manuales y datos de terceros

- Estado: Propuesta
- Fecha: 2026-09-29
- Revisado: 2026-10-04, con los ajustes del asesor (principio «local completo, nube mínima y configurable»; ver «Revisión del 2026-10-04»)
- Participantes: investigador doctoral, asesor (Claude en Cowork) y Claude Code

## Contexto

El hito 2 convierte las exportaciones de las bases con acceso institucional
(Scopus, Web of Science y ACS Publications) en registros normalizados con
procedencia, y registra cada búsqueda manual para el diagrama de flujo y el
reporte (PRISMA-ScR, ítems 7 y 8). La especificación está en
[hito_2_registros_e_importacion.md](../especificaciones/hito_2_registros_e_importacion.md).

Tres hechos obligan a decidir antes de programar:

- **Las exportaciones contienen datos de terceros con licencia.** El
  ADR-0004 (punto 8) versiona «todo lo anterior» en el repositorio del
  estudio, y `arquitectura.md` decía que `importaciones/` guarda los
  archivos originales. Pero los resúmenes y los campos que agrega cada base
  están protegidos por sus términos de uso, y el repositorio de un estudio
  se publica: el de demostración ya es público, y el del caso piloto se
  publica y se archiva en Zenodo al final (ADR-0007, puntos 3 y 19).
- **La unidad de trabajo es la búsqueda, no el archivo.** Una búsqueda se
  exporta en varios archivos cuando supera el máximo por exportación (p. ej.
  1 000 registros en Web of Science), y PRISMA-ScR pide la fecha y la
  estrategia completa de cada búsqueda.
- **ACS Publications se agregó como fuente manual** (ADR-0003, nota
  posterior), con una interfaz sin cuadro de ecuación y sin la exportación
  masiva de las otras dos bases.

Las opciones de cada decisión se presentaron al investigador con pros,
contras y una recomendación. El investigador y el asesor eligieron el
2026-09-29 (decisiones D1 a D6 del plan del hito 2 y N1 a N8 de la
verificación). Las no elegidas están en «Alternativas consideradas».

### Revisión del 2026-10-04

El asesor revisó la propuesta y esta versión incorpora sus ajustes:

- el principio de diseño «local completo, nube mínima y configurable», con la
  publicación de campos decidida por cada estudio y no por una tabla única del
  paquete (puntos 1 a 4);
- los campos pendientes de confirmar ya no bloquean `importar registrar`:
  solo impiden versionarlos (punto 4);
- la regla de la evidencia literal, que resuelve la contradicción entre «el
  resumen no se publica» y «la evidencia de una decisión se versiona»
  (punto 5);
- el respaldo de los originales se separa de lo que se publica (punto 9);
- la ruta `adaptacion_generica` solo se prueba con datos sintéticos (punto 12);
- los máximos de exportación y las cláusulas de términos de uso quedan
  marcados «por verificar» (puntos 25 y 26).

## Decisión

### Principio de diseño: local completo, nube mínima y configurable

- **Local completo.** El equipo del investigador conserva todo completo: los
  originales, los registros completos regenerados, los lotes, las hojas y la
  evidencia literal.
- **Nube mínima.** En el repositorio del estudio (público o privado) solo va lo
  mínimo que la licencia de la fuente permite y que hace falta para auditar.
- **Configurable.** Cada estudio habilita, en su configuración, qué campos de
  cada fuente son publicables, y **registra la base** de esa habilitación: la
  institución que la confirmó, la política de la revista o editorial, o la
  licencia de los datos.
- **Nunca publicables,** sin configuración posible: el resumen, las palabras
  clave (de autor o indexadas, Keywords Plus), las referencias citadas, los
  conteos de citas, las afiliaciones y la financiación. La única salida de
  texto derivada del resumen que admite este ADR es la cita breve de la
  evidencia literal, con las condiciones del punto 5.

### Datos de terceros: dos niveles

1. **Qué se versiona y qué no.**
   - **Se versionan:** los datos de cada búsqueda (evento y
     `importacion.json`), el hash y el número de registros de cada archivo
     original, el hash de la configuración de publicación vigente, y los
     registros normalizados **restringidos a los campos habilitados por el
     estudio con su base registrada** (punto 4).
   - **No se versionan, en ningún repositorio, público ni privado:** las
     exportaciones originales y los registros completos (con resumen,
     palabras clave y demás campos restringidos). El historial publicado de
     Git no se reescribe, así que un original versionado por error quedaría
     publicado para siempre.
2. **Registro completo local y regenerable.** El registro completo vive en el
   equipo del investigador: el original que el paquete copia a
   `exportaciones_originales/` es la copia local completa, y el registro
   completo normalizado se regenera leyéndolo, después de comprobar que su hash
   coincide con el registrado. El registro versionado guarda además el hash del
   registro completo normalizado, para comprobar que la regeneración da
   exactamente el mismo registro. Un campo que no se versiona (porque no está
   habilitado o porque su base está pendiente) **sí se importa y se conserva
   en local**: lo que se restringe es la publicación, no la importación.
3. **Este ADR modifica el alcance del ADR-0004.** Lo reproducible
   («a partir de los artefactos registrados, volver a ejecutar el pipeline
   produce exactamente los mismos conteos, tablas, gráficos y reportes») pasa
   a ser: **lo versionado más las exportaciones originales verificadas por su
   hash.** Un tercero reproduce sin los originales todo lo que depende solo
   de campos versionados (conteos por fuente, deduplicación por DOI,
   diagrama de flujo, tabla de estudios). Lo que depende de campos no
   versionados (los lotes del cribado, la verificación de la evidencia
   literal tomada de un resumen y, si el estudio no los habilita, los
   prefiltros por año, idioma o tipo de documento) exige los originales, que
   conserva el investigador. El reporte debe declararlo. Para las respuestas
   crudas de las APIs rige lo mismo: la reproducción se apoya en la copia
   local y en los hashes registrados, no en respuestas crudas publicadas. El
   ADR-0003 y el ADR-0004 recibieron una nota posterior del 2026-10-04 que
   remite aquí.
4. **Política de campos en dos niveles.** La regla es general: sirve para las
   exportaciones de este hito y para las respuestas crudas de las APIs del
   hito 3 (hoja de ruta, nota del hito 3).
   - **Paquete: `agentresearch/registros/politica_datos.yaml`.** Es una tabla
     de datos, no código: cambiarla no exige tocar el código, pero sí una
     versión nueva del agente. Contiene la lista fija de campos
     `nunca_publicables` (arriba) y, por fuente, los **campos que esa fuente
     puede aportar y que el estudio puede habilitar** (por ejemplo, el
     identificador de la base: EID en Scopus, UT en Web of Science). **El
     paquete es neutral:** no atribuye ninguna confirmación a una institución
     ni trae una base por omisión, porque eso es de cada estudio. Que un campo
     esté «confirmado» o «pendiente» lo decide la base que el estudio registre
     para él (abajo), no esta tabla.
   - **Estudio: `publicacion_datos.yaml`,** en la raíz del estudio y
     versionado. Por fuente, lista los campos habilitados, y cada uno con su
     `base`: `tipo` (`institucion`, `revista` o `licencia`), `detalle` (la
     institución, la revista o la licencia concreta), `medio` y `fecha`. El
     paquete rechaza al cargarla cualquier campo `nunca_publicables`. Cada
     importación registra el hash de este archivo y el de la política del
     paquete. **La plantilla lo genera neutro:** con los campos de metadatos
     bibliográficos habituales (título, autores, DOI y fuente de publicación)
     y su base incompleta (`detalle`, `medio` y `fecha` vacíos), hasta que el
     investigador registre la suya.
   - **Regla de versionado.** Un campo se versiona solo si no es
     `nunca_publicables`, el estudio lo habilita para esa fuente y su base está
     completa. Una fuente sin entrada no tiene campos habilitados por omisión:
     el estudio los habilita registrando la base.
   - **Ejemplo documentado: el caso del investigador (Universidad del
     Cauca).** No es un dato del paquete ni de la plantilla; es lo que su
     estudio registrará en `publicacion_datos.yaml`:
     - **Confirmados por la Biblioteca de la Universidad del Cauca:** título,
       autores, DOI y revista o fuente de publicación. **Pendiente de
       completar por el investigador:** el medio y la fecha de la
       confirmación, y las bases que cubre (Scopus, Web of Science, ACS).
     - **Pendientes de confirmar con la Biblioteca** (no se consultaron): año,
       volumen, número, páginas, tipo de documento, idioma y el identificador
       de la base (EID en Scopus, UT en Web of Science, ID de Lens). Si la
       respuesta es no, no se habilitan, o se completan en el hito 3 desde
       Crossref u OpenAlex, cuyos metadatos son CC0 (la base sería
       `licencia`).
   - **Lo pendiente no bloquea.** `importar registrar` ya no se niega por
     campos sin base: los importa y los conserva en local, informa cuáles se
     versionan y cuáles quedan solo en local (advertencia I-A01) y registra
     ambas listas en el evento. Así ningún dato real se versiona sin base, y la
     importación no espera a una respuesta externa. `importar leer`
     funciona igual.
   - **Ampliar o reducir.** Habilitar más campos después se aplica a las
     importaciones nuevas; regenerar las ya registradas exigirá un comando que
     queda fuera del hito 2 (ver «Consecuencias»). Retirar un campo que ya se
     publicó no lo despublica: el historial de Git no se reescribe.
5. **Consecuencias para los hitos siguientes,** que este ADR fija como
   principio:
   - hito 3: las respuestas crudas de las APIs siguen esta política; las
     respuestas completas quedan en una carpeta local ignorada por Git, y se
     versionan su hash y los campos habilitados (hoja de ruta, nota del
     hito 3). Los resúmenes de Crossref no se versionan;
   - hito 5: los lotes de entrada del LLM y las hojas Excel de revisión
     contienen resúmenes, así que no se versionan; se versionan su hash y
     los IDs de sus registros, y se regeneran desde los originales
     (exportaciones o respuestas crudas);
   - **evidencia literal (hito 5): regla.** El resumen nunca se publica, pero
     cada decisión cita un fragmento literal del registro (CLAUDE.md, regla 2;
     ADR-0004, puntos 1 y 2). Se concilian así:
     1. La evidencia es una cita breve de un campo del registro, nunca el
        campo completo.
     2. Si el fragmento sale de un campo habilitado (p. ej. el título), su
        texto se versiona.
     3. Si sale del resumen, de las palabras clave o de otro campo no
        habilitado, el texto del fragmento se versiona **solo si
        `publicacion_datos.yaml` lo permite** (`evidencia_literal`, con su
        base registrada) y no supera la longitud máxima que `registrar` valida
        (valor que fija el hito 5). Por omisión no se permite.
     4. Con cualquier configuración, la decisión versionada guarda el campo de
        origen, las posiciones de inicio y fin del fragmento y su SHA-256, de
        modo que quien tenga el original verifica la evidencia sin que el
        texto esté publicado. El texto del fragmento queda siempre en el
        registro local de decisiones, ignorado por Git (el hito 5 diseña el
        archivo y su anclaje a la cadena de eventos).
     5. La permisión y la longitud máxima son una decisión del estudio y no
        una conclusión jurídica sobre si la cita es un uso legítimo.

     Sin el original, un tercero no puede verificar contra el resumen una
     evidencia cuyo texto no se publicó; el reporte lo declara.

### Dónde viven los originales

6. **Carpeta ignorada fija.** Al registrar, el paquete **copia** cada
   archivo exportado a `exportaciones_originales/imp-NNNN/` dentro del
   estudio, con su nombre original. El `.gitignore` de la plantilla ignora
   esa carpeta, y llega al estudio con `estudio actualizar` antes de su
   primera importación. El evento guarda la ruta relativa y el hash de cada
   copia, para que los hitos 4 y 5 regeneren los registros completos sin
   pedir rutas al investigador.
7. **Comprobación con `git check-ignore`.** Antes de escribir,
   `importar registrar` ejecuta `git check-ignore` sobre cada ruta de
   destino y sobre el archivo de origen si está dentro del estudio. Según
   la documentación de Git (2.52.0), sale con 0 si la ruta se ignora, con 1
   si no y con 128 ante un error fatal, y por defecto un archivo ya
   agregado al índice no cuenta como ignorado. El comando solo continúa con
   0; con 1, 128, sin Git instalado o fuera de un repositorio, se niega
   **sin escribir nada** y explica cómo corregirlo.
8. **Excepción al principio de no depender de Git.** El ADR-0007 (punto 6)
   y el ADR-0008 decidieron que el paquete no depende de Git. Esta es la
   única excepción: solo `importar registrar` lo usa, y solo para
   comprobar que un original no quedará versionado. Leer, validar y el
   historial siguen sin Git. Se prefirió a comprobar el `.gitignore` como
   texto, que no ve las reglas globales, las negaciones ni los archivos ya
   agregados.
9. **Copias de respaldo: independientes de lo que se publica.** Qué campos
   se publican (punto 4) y dónde se guarda el respaldo son decisiones
   distintas, y la confirmación de la Biblioteca sobre lo primero no dice nada
   sobre lo segundo. Lo segundo depende de los **términos de almacenamiento de
   cada fuente y del contrato de la institución** (punto 26, por verificar).
   - Por omisión, `/importar` recuerda guardar cada original en el equipo y
     en un respaldo fuera de los servicios de nube compartidos (p. ej. un
     disco externo).
   - La nube institucional solo se recomienda para una fuente si el estudio
     registra en su configuración (`respaldo_nube: permitido`, con su base:
     el término del contrato o la confirmación de la institución, el medio y
     la fecha). Para ACS no se recomienda: la licencia individual prohíbe
     guardar sus contenidos en servicios de nube compartidos (punto 26).
   - El hash prueba que las copias son idénticas al original registrado.

### Unidad de importación: la búsqueda manual

10. **Qué registra cada búsqueda** (hoja de ruta, nota del hito 2):
    - la fuente, que debe estar declarada en `fuentes` del protocolo con
      `tipo: exportacion`; la plataforma, la institución de acceso y la
      cobertura disponible (p. ej. las ediciones y los años de Web of Science
      Core Collection), y el estado de la opción de lematización si la
      interfaz la ofrece;
    - los filtros aplicados en la interfaz;
    - la fecha y hora de la búsqueda, con su desfase y en UTC (punto 13);
    - la ecuación esperada y la ejecutada (punto 12);
    - el número de resultados que mostró la interfaz, el número de registros
      leídos y, si difieren, una justificación;
    - cada archivo: nombre original, formato, hash, número de registros y
      ruta de su copia.
11. **Solo con el protocolo vigente.** `importar registrar` se niega si el
    protocolo no está vigente según el registro, si hay P-E09 o P-E10, si la
    fuente no está declarada con `tipo: exportacion`, o si la fecha de la
    búsqueda es futura o anterior a la aprobación.
12. **Ecuación esperada y ejecutada.**
    - **Esperada:** la de esa fuente para la versión del protocolo vigente
      en la fecha de la búsqueda (la última aprobación o enmienda con fecha
      anterior). Se toma de `protocolo/ecuaciones.md` si su cabecera tiene
      el hash de esa versión; si no, se genera desde
      `protocolo/versiones/X.Y.Z.yaml` con el agente instalado, y el
      registro lo indica. Para una fuente sin traductor, la esperada es la
      genérica.
    - **Ejecutada:** el texto que el investigador ejecutó en la interfaz
      (en ACS, la consulta que la página muestra sobre los resultados).
    - Se guardan el texto completo y el hash de ambas, porque
      `ecuaciones.md` se regenera. La relación entre ellas es una de tres:
      - `identica`;
      - `desviacion`: una fuente con traductor (Scopus, Web of Science)
        cuya ecuación se modificó en la interfaz. Exige justificación, y el
        reporte la declara (PRISMA-ScR, ítem 8);
      - `adaptacion_generica`: una fuente sin traductor (ACS, Lens, AGRIS)
        que parte de la genérica. No es una desviación. **Esta ruta solo se
        prueba con datos sintéticos hasta tener datos reales:** el estudio
        de demostración no usa ACS (punto 27) y la exportación de prueba de
        ACS del 2e solo se lee con `importar leer`, sin registrarla. Su
        primer uso real será el de un protocolo que declare una fuente sin
        traductor (p. ej. el del caso piloto, hito 11).
13. **Fecha y hora.** La terminal pide la fecha (`AAAA-MM-DD`) y la hora
    (`HH:MM`) por separado y propone el desfase del computador para esa
    fecha, que el investigador confirma o corrige (`±HH:MM`). Se guardan la
    hora local con su desfase (ISO 8601) y la hora UTC. Sin dependencias:
    según la documentación de Python 3.12, `astimezone()` sobre una fecha
    sin zona la toma como hora local del sistema, con el desfase que da el
    sistema operativo. Si el desfase de la fecha de la búsqueda difiere del
    actual (otro periodo de horario de verano), la terminal lo avisa.
14. **Varios archivos por búsqueda.**
    - La suma de los registros de todos los archivos se compara con los
      resultados de la interfaz; si difieren, se exige justificación.
    - Un mismo identificador de la fuente repetido, dentro de un archivo o
      entre archivos de la búsqueda, es un error: indica tandas solapadas o
      una descarga repetida.
    - Cada archivo pertenece a una sola búsqueda: un archivo cuyo hash ya
      está registrado en el estudio se rechaza. Una descarga repetida con
      otro hash (p. ej. un RIS de ACS, cuyo campo `Y2` es la fecha de
      descarga) la detecta el identificador repetido.
    - Sin identificador de la fuente ni DOI, un registro no se puede
      comparar; `importar leer` lo avisa.
15. **Dos subcomandos** (el ADR-0007, punto 15, explica por qué no sirve una
    opción `--simular`: una regla `deny` gana sobre una `allow`):
    - `importar leer`: lee, cuenta e informa, sin escribir nada. Se permite a
      Claude Code;
    - `importar registrar`: registra la búsqueda. Exige una terminal
      interactiva y un revisor humano declarado, como `aprobar` (ADR-0008,
      punto 11), y los permisos del estudio lo niegan a Claude Code. Los
      datos que solo conoce el investigador los declara él y los confirma en
      su terminal.

### Evento y archivos

16. **Evento `busqueda_registrada` en `protocolo/eventos.jsonl`.** No se
    renombra `protocolo/`. El principio: esa cadena guarda los **eventos del
    estudio**, que son pocos (creación, actualizaciones, ciclo de vida del
    protocolo, búsquedas). Las decisiones masivas del hito 5 van en su
    propio archivo, anclado a esta cadena. El evento lleva los datos del
    punto 10, el hash de `importacion.json`, `registros.jsonl` y
    `registros.csv`, el hash de la política del paquete y el de
    `publicacion_datos.yaml`, y las listas de campos versionados y
    campos solo locales (punto 4). Se valida con un
    esquema pydantic estricto, y P-E10 incorpora su coherencia: números de
    importación consecutivos y archivos con los hashes registrados.
17. **Una carpeta por importación**, `importaciones/imp-NNNN/`:
    - `importacion.json`: los datos de la búsqueda;
    - `registros.jsonl`: un registro normalizado por línea, en JSON canónico
      (ADR-0006, punto 2), solo con los campos versionables según el
      punto 4;
    - `registros.csv`: una vista derivada y determinista de
      `registros.jsonl`, con columnas fijas.
18. **Atomicidad.** El evento es el punto de confirmación, como en el
    ADR-0008 (punto 14): primero las copias de los originales y los archivos
    de `importaciones/imp-NNNN/`, después el evento y al final el anclaje.
    Si algo falla antes del evento, la carpeta queda huérfana y el siguiente
    intento la sobrescribe con el mismo número.
19. **Procedencia.** Cada registro guarda su importación, su posición (el
    archivo y la línea o fila) y el identificador de la fuente: EID en
    Scopus, UT en Web of Science, DOI en ACS, PMID en PubMed e ID de Lens.
20. **Hash del registro normalizado.** Se calcula sobre el JSON canónico de
    los campos del esquema normalizado, que nunca incluye campos volátiles
    (la fecha de descarga `Y2` del RIS de ACS, la fecha de generación del
    archivo en Web of Science). Así, el mismo registro descargado dos veces
    tiene el mismo hash.

### Modelo de datos

21. **Registro, artículo y estudio** (Kitchenham et al., 2011; regla 7 de
    CLAUDE.md). El **registro** es lo que devuelve una fuente; el
    **artículo**, la publicación, a la que la deduplicación (hito 4) asocia
    uno o varios registros; el **estudio**, la investigación, con una
    relación de muchos a muchos con los artículos (hito 8). Los esquemas de
    artículo y estudio quedan **provisionales** hasta los hitos 4 y 8.
22. **El registro admite patentes (Lens) y tesis:** no exige DOI ni revista.
    Los valores se guardan como se leyeron, con normalizaciones mínimas y
    deterministas: espacios, Unicode NFC, tildes de LaTeX en BibTeX y el DOI
    (se extrae la forma `10.…` de cualquier URL, incluido el proxy de la
    biblioteca, y se pasa a minúsculas ASCII, porque el DOI Handbook, §2.4,
    define el DOI como insensible a mayúsculas ASCII). Ningún registro se
    inventa ni se corrige a mano (regla 6).

### Lectores

23. **Lectores propios con la biblioteca estándar** para RIS, Web of Science
    (texto plano con etiquetas), CSV de Scopus y CSV genérico con un archivo
    de mapeo de columnas. Leen las columnas por nombre y nunca por posición,
    toleran el BOM y el fin de línea CRLF, e informan cada error con su
    número de línea. El RIS de ACS trae líneas de cabecera antes del primer
    `TY` (`Provider:`, `Database:`, `Content:`), que se toleran y se
    informan.
24. **BibTeX con `bibtexparser==2.0.1` y `pylatexenc==2.11`,** con la versión
    exacta fijada, detrás de una interfaz de lector propia para poder
    cambiarla sin tocar el resto. Verificado en PyPI el 2026-09-29:
    bibtexparser es MIT y «Production/Stable»; la 2.0.0 (2026-09-08) llegó
    tras diez versiones beta desde 2023, y la 2.0.1 (2026-09-10) solo cambia
    documentación. Su única dependencia, pylatexenc (`~=2.10`), es MIT y
    estable (2.11, 2026-07-25), sin dependencias propias. Si las pruebas
    sintéticas revelan fallos, se reemplaza por un lector propio del
    subconjunto que exportan las bases.
25. **Máximo por exportación** (consultado el 2026-09-29; **por verificar**
    en la plataforma antes de apoyarse en él: el artículo de Clarivate es de
    2022 y los límites dependen de la plataforma y del contrato). Hasta
    entonces, `/importar` los muestra como «según la documentación
    consultada, por verificar»:

    | Base | Máximo | Estado | Fuente |
    |---|---|---|---|
    | Scopus | 20 000 elementos en CSV, RIS, BibTeX y texto plano; BibTeX no incluye «Funding Details» ni «Other Information» | por verificar | [Scopus Support Center](https://www.elsevier.support/scopus/answer/how-do-i-export-documents-from-scopus) (act. 2026-04-21) |
    | Web of Science | 1 000 con el registro completo; 500 con las referencias citadas. «Fast 5000» solo trae autor, título y fuente, sin resumen: no sirve para el cribado | por verificar | [Clarivate](https://support.clarivate.com/ScientificandAcademicResearch/s/article/Web-of-Science-Limit-on-exporting?language=en_US) (2022-04-20); [Marked Lists](https://webofscience.zendesk.com/hc/en-us/articles/20135824927505-Saving-and-Exporting-Marked-Lists) |
    | ACS | no documentado; según la prueba del investigador, no hay descarga masiva desde los resultados | no documentado | punto 28 |

    La verificación se hace con las exportaciones reales de prueba del 2e
    (parte A): el investigador anota en la interfaz el máximo que ofrece.

### Términos de uso (consultados el 2026-09-29)

26. **Lo que dicen los términos públicos (todo por verificar).** El contrato
    de la Universidad del Cauca con cada proveedor prevalece y no es público;
    lo que sigue son los términos públicos y licencias tipo consultados el
    2026-09-29, y **cada cláusula está por verificar** contra el contrato de la
    institución (la Biblioteca) antes de apoyarse en ella. Una licencia de
    muestra de otra institución, como la de Scopus de abajo, no prueba lo que
    dice el contrato propio.
    - **Scopus (Elsevier).** La licencia tipo de suscripción prohíbe usar
      robots y reproducir, retener o redistribuir de forma sustancial o
      sistemática ([ejemplo de licencia](https://www.czechelib.cz/default/files/download/id/268/elsevier-v-scopus-sla-20191209.pdf)).
      La política de uso de la API para investigación académica no permite
      mostrar datos de Scopus «on a website or in any other public forum»
      fuera de la obra publicada, y los resúmenes nunca se muestran en
      público ([dev.elsevier.com/policy.html](https://dev.elsevier.com/policy.html)).
    - **Web of Science (Clarivate).** Los Clarivate Terms, §3, permiten el
      uso «solely for internal analysis and research purposes», descargar
      «reasonable amounts» y distribuir solo «limited extracts» sin valor
      comercial propio ([Clarivate Terms](https://d7umqicpi7263.cloudfront.net/eula/qWD3UnrYZjfCFlip54PGHN7qvqKWgT0gBRPNJ4qWqt0),
      enlazados desde el [Legal Center](https://clarivate.com/legal-center/terms-of-business/)).
    - **ACS Publications.** La licencia individual prohíbe guardar los
      contenidos en servicios de nube compartidos (3.5), la descarga
      sistemática (3.8) y las herramientas automatizadas (3.9)
      ([EULA](https://pubs.acs.org/pages/eula)). El acuerdo institucional
      prohíbe el almacenamiento para uso de toda la institución y la
      actividad que indique «an otherwise manual process being automated»
      ([acuerdo institucional](https://solutions.acs.org/wp-content/uploads/2021/04/ACS-Publications-Institutional-Access-Agreement-Academic.pdf)).
    - **El agente nunca automatiza estas interfaces** con las credenciales
      del investigador (ADR-0003, nota posterior): el investigador busca y
      exporta a mano.

### ACS Publications

27. **Rol de ACS (decisión del investigador, 2026-09-29).** ACS no es una
    base de búsqueda principal:
    - el agente lee su RIS para **búsquedas complementarias puntuales**,
      descargadas por selección o por página y registradas como tandas de
      una misma búsqueda (punto 14);
    - su **uso principal previsto es conseguir textos completos en el
      hito 7**, descargados a mano y uno por uno, porque sus términos
      prohíben la descarga sistemática (punto 26);
    - **el estudio de demostración no usa ACS como base de búsqueda.** Su
      protocolo no la declara, así que no requiere enmienda. La exportación
      de prueba del criterio de terminado (un RIS de uno a tres registros) se
      lee con `importar leer` en el repositorio del agente.
28. **Interfaz verificada.**
    - **Documentación oficial** (los «Search Tips» de
      [pubs.acs.org/search/advanced](https://pubs.acs.org/search/advanced),
      2026-09-29): AND, OR y NOT dentro de un campo, con AND por defecto;
      comillas para frase exacta; `?` y `*`, que no se admiten al inicio de
      un término ni dentro de una frase entre comillas.
    - **Pruebas del investigador en la interfaz** (2026-09-29):

      | Prueba | Resultado | Conclusión |
      |---|---|---|
      | Campos | All, Title, Author, Author affiliations, Full text, Abstract, Keyword, DOI, ISBN, eISBN, ISSN, eISSN, Issue, Volume, References | hay título, resumen y palabras clave por separado; ningún campo los combina |
      | Frase de la sección de métodos de un artículo abierto | All: 1; Abstract: 0 | «All» busca en el texto completo |
      | `(coffee OR cocoa) AND mucilage`, sin paréntesis, y cada par por separado (Abstract) | 4; 1; 3 y 1 | los paréntesis funcionan dentro de una fila (4 = 3 + 1); sin ellos el resultado no sigue una precedencia estándar |
      | `mucilage`, `mucilages`, `"mucilage"` (Title) | 50, 50, 50 | ACS lematiza, y las comillas no lo desactivan en una palabra suelta |
      | Dos filas (Title, Abstract) con AND, OR y NOT | 2; 837; 768 | las filas se combinan como conjuntos: la fila de Abstract tiene 837 − 768 = 69, la de Title 768 + 2 = 770, y 770 + 69 − 2 = 837 |
      | `"coffee mucilag*"` | 832 | no concluyente; se aplica la documentación oficial: sin comodín en frases |

      Una segunda prueba de frase dio más de un millón de resultados en All,
      lo que no es posible con una frase exacta de seis palabras; se descarta
      (probablemente comillas tipográficas).
    - **RIS de ACS** (plataforma Silverchair): cabecera antes de `TY`, título
      en `T1`, año en `PY`, fecha de publicación en `Y1`, fecha de descarga
      en `Y2`, resumen en `AB`, DOI en `DO`.
    - **Pendiente de completar por el investigador** (comprobación
      adicional): si hay botón de descarga para los resultados
      seleccionados, cuántos resultados muestra cada página, si hay una
      casilla para seleccionar toda la página y si existe una opción de
      lematización.
29. **Ecuación de ACS: genérica con un aviso propio, sin traductor.** Si el
    protocolo declara la fuente `acs`, su entrada en «Fuentes sin
    traductor» de `ecuaciones.md` agrega un aviso con lo verificado:
    - usar siempre los paréntesis;
    - no usar «All», que incluye el texto completo y cambia el alcance
      frente a las demás fuentes (ADR-0009, punto 16);
    - usar las variantes en lugar de `*` dentro de frases;
    - ACS lematiza y las comillas no lo desactivan;
    - **receta opcional verificada, por filas:** una fila por campo (Title,
      Abstract y Keyword), cada una con la ecuación completa entre
      paréntesis, unidas con OR. Solo usa OR entre filas, así que no depende
      de una precedencia. **Limitación:** es más estrecha que
      `TITLE-ABS-KEY(A AND B)`, porque no recupera un registro con el
      bloque A en el título y el bloque B solo en el resumen.

    La búsqueda se registra como adaptación de la genérica (punto 12) y
    guarda el estado de la opción de lematización si ACS la ofrece. El
    `ecuaciones.md` de un protocolo sin `acs` no cambia.
30. **Cobertura de ACS en Scopus y Web of Science: no se afirma.** No se
    pudo verificar en las fuentes oficiales (la lista de fuentes de Scopus y
    la Master Journal List de Clarivate exigen sesión), y solo se
    encontraron sitios de terceros. Si una decisión futura lo necesita (p.
    ej. el protocolo del caso piloto en el hito 11), se verifica antes en
    esas dos listas.

## Alternativas consideradas

- **Versionar las exportaciones originales** (lo que decía
  `arquitectura.md`): es lo más simple y reproducible, pero publica
  resúmenes y campos protegidos, y el historial de Git no se reescribe.
- **Campos versionados:**
  - todo menos el resumen: incluiría campos que agrega la base (términos
    indexados, Keywords Plus, citas, afiliaciones), que la consulta a la
    Biblioteca no cubrió;
  - solo identificadores: riesgo mínimo, pero el repositorio público no
    mostraría qué se encontró, y la tabla de estudios dependería de
    completar los metadatos desde otra fuente.
- **Una tabla única del paquete que fija los campos publicables de todos los
  estudios** (la versión del 2026-09-29): simple, pero la licencia y la
  confirmación de la fuente dependen de la institución y de la revista, no del
  paquete, y un estudio con otra base no podría habilitar un campo sin una
  versión nueva del agente.
- **Negarse a registrar mientras haya campos pendientes** (la versión del
  2026-09-29): garantiza que nada sin confirmar se versione, pero ata la
  importación a una respuesta externa. Se prefirió importar todo en local y
  restringir solo la publicación.
- **Evidencia literal: versionar siempre el fragmento, o no versionarlo
  nunca.** Siempre publica texto del resumen sin una decisión del estudio;
  nunca rompe la regla 2 de CLAUDE.md en el repositorio público. Se eligió
  la configuración por estudio, con el hash y las posiciones siempre
  versionados.
- **Dónde viven los originales:**
  - siempre fuera del estudio, sin Git: no hay ambigüedad, pero los hitos 4
    y 5 tendrían que pedir la ruta de cada original;
  - comprobar el `.gitignore` como texto: no ve las reglas globales, las
    negaciones ni los archivos ya agregados.
- **Copias de respaldo:** solo locales (se pierden con el equipo); nube
  institucional para todas las bases (la licencia individual de ACS lo
  prohíbe para sus contenidos); decidir el respaldo según la confirmación de
  la Biblioteca sobre los campos publicables (mezcla dos cuestiones
  distintas: qué se publica y dónde se guarda).
- **Una opción `--simular` en lugar de dos subcomandos:** una regla `deny`
  sobre el comando bloquearía también la simulación (ADR-0007, punto 15).
- **El archivo, y no la búsqueda, como unidad:** no representa las búsquedas
  exportadas en tandas, y PRISMA-ScR reporta búsquedas.
- **Validar las tandas con rangos declarados (1–1000, 1001–2000):** más
  control, pero más datos que el investigador debe anotar; la suma y el
  identificador repetido detectan las omisiones y los solapamientos.
- **Fecha y hora:** un nombre de zona IANA exigiría la dependencia `tzdata`,
  porque Windows no trae esa base (documentación de Python 3.12); una zona
  fija (`America/Bogota`) no serviría a otros investigadores.
- **Evento en un archivo propio de importaciones:** dispersaría la línea de
  tiempo del estudio; la cadena de eventos tiene pocos eventos y ya tiene
  anclaje.
- **BibTeX:** un lector propio del subconjunto de las bases (sin
  dependencias, pero la decodificación de LaTeX es donde un lector propio
  falla) y bibtexparser 1.4.4 (la API antigua).
- **Ecuación de ACS:**
  - un traductor propio para una sola fila: el alcance de los campos y la
    precedencia sin paréntesis no están documentados, y el ADR-0009 trata lo
    no documentado como no admitido;
  - instrucciones completas por filas como si fueran un traductor: la
    versión por filas es más estrecha que las demás fuentes; se ofrece solo
    como receta opcional.
- **ACS sin exportación masiva:** el conector de Zotero desde la página de
  resultados. Los registros serían la versión que arma el traductor de
  Zotero y no la exportación de ACS, y Zotero puede descargar los PDF de
  forma automática, lo que los términos de ACS prohíben.

## Consecuencias

- El repositorio público de un estudio no contiene resúmenes ni campos
  restringidos. Un tercero reproduce los conteos y la deduplicación por DOI
  sin los originales; lo que depende de los resúmenes exige los originales,
  y el reporte lo declara.
- El investigador es responsable de conservar los originales (equipo y
  respaldo). Sin ellos, los hitos 4 y 5 no pueden regenerar los registros
  completos. `importar historial` informa qué originales faltan en el equipo.
- `importar registrar` depende de Git y de que el `.gitignore` del estudio
  ignore `exportaciones_originales/`: el estudio de demostración debe pasar a
  `v0.2.0` con `estudio actualizar` antes de su primera importación, y esa
  actualización, con el protocolo vigente, es una desviación que el reporte
  declara (ADR-0007, punto 20).
- Los campos pendientes de confirmar no bloquean el registro de una búsqueda:
  se importan en local y no se versionan hasta que el estudio registre su
  base (punto 4). La confirmación de la Biblioteca (medio, fecha y bases que
  cubre) se completa aquí cuando el investigador la tenga, y no es un
  requisito del sub-hito 2e.
- Queda pendiente, fuera del hito 2, un comando que regenere las
  importaciones ya registradas cuando el estudio habilite más campos
  (punto 4, «Ampliar o reducir»). Se decide con el hito 4 o el 5, cuando haya
  una necesidad real.
- La evidencia literal de las decisiones sin texto publicado no es verificable
  por un tercero sin los originales (punto 5); el reporte lo declara.
- `arquitectura.md` se actualiza con la estructura nueva
  (`importaciones/imp-NNNN/` y `exportaciones_originales/`) y con la política
  de los lotes y las hojas del hito 5.
- `ecuaciones.md` cambia solo para los protocolos que declaran `acs`.
- Si Scopus, Clarivate o ACS cambian sus términos o sus límites, hay que
  revisar la política de campos y la tabla del punto 25. Mientras sigan «por
  verificar» (puntos 25 y 26), ninguna decisión del agente debe apoyarse en
  esos límites ni en esas cláusulas.
