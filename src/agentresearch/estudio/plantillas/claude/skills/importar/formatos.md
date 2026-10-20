# Formatos de los archivos que preparas

Todos van en `.borradores/`, en UTF-8, y su contenido queda en los eventos. Los lee el comando de forma estricta: una clave desconocida es un error.

## `.borradores/busqueda.json`

```json
{
  "fuente": "scopus",
  "plataforma": "Scopus (interfaz web)",
  "institucion_acceso": "Nombre de la institución desde la que se accedió",
  "cobertura": "Años o colecciones cubiertas por la suscripción",
  "lematizacion": "No aplica",
  "filtros": ["Años 2015–2026", "Tipo de documento: artículo"],
  "ecuacion_ejecutada": "La ecuación tal como la ejecutó, copiada de la interfaz",
  "justificacion_ecuacion": "",
  "resultados_interfaz": 466,
  "justificacion_diferencia": "",
  "formato": "ris",
  "mapeo": null,
  "archivos": ["../exportaciones/scopus-2015-2020.ris", "../exportaciones/scopus-2021-2026.ris"]
}
```

- `fuente`: el identificador declarado en el protocolo (`scopus`, `wos`, `acs`…).
- `lematizacion`: texto libre o `null` si la pregunta no aplica.
- `justificacion_ecuacion`: obligatoria si la ecuación ejecutada difiere de la esperada en una fuente con traductor; vacía si es idéntica.
- `resultados_interfaz`: el número que mostró la base. `justificacion_diferencia`: obligatoria si la suma de registros leídos no coincide.
- `formato`: `ris`, `bibtex`, `scopus_csv`, `wos_txt` o `csv`.
- `mapeo`: ruta del archivo de mapeo; **obligatorio solo con `csv`** y no admitido con otro formato.
- `archivos`: rutas de los archivos exportados, una por tanda. Solo sirven para leerlos: el comando copia cada original a `exportaciones_originales/imp-NNNN/` y nunca guarda las rutas.
- La fecha y la hora **no** van aquí: las pide la terminal.

## Archivo de mapeo (solo con `--formato csv`)

JSON de un solo nivel, `{"columna": destino}`, donde `destino` es:

- un campo del esquema: `"titulo"`, `"fuente_publicacion"`, `"volumen"`, `"numero"`, `"paginas"`, `"doi"`, `"pmid"`, `"tipo_documento"`, `"idioma"`, `"resumen"`, `"anio"`;
- un objeto `{"campo": "autores", "separador": "; "}`, obligatorio para los campos de lista (`autores`, `palabras_clave_autor`, `palabras_clave_indexadas`);
- `"id_fuente:TIPO"`, con `TIPO` en `eid`, `ut`, `doi`, `pmid` o `lens_id`.
