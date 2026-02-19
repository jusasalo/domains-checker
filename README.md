# Domains Checker

Herramienta CLI en Python para validar si estas disponibles o tomados (`taken`/`available`) y devolver con quien se hizo el registo.
Tambien puede verificar si variantes del dominio con letras en vez de numeros, tambien estan disponibles.

![Domains Checker](images/domains-checker-demo.png)

## ¿Qué hace este proyecto?

- Lee dominios base y TLDs desde `domains.json`.
- Genera candidatos:
  - `dominio.com`
  - `dominio.net`
  - `dominio.site`
  - `dominio.org`
  - `dominio.app`
  - `dominio.etc`
  - variantes tipográficas según `config.json`.
  - No genera ni consulta subdominios (por ejemplo `www.*`).
- Ejecuta chequeos concurrentes:
  - DNS
  - HTTP/HTTPS
  - TLS (si aplica)
  - Registrar (RDAP) para `registrar_name`, `registrar_url` y `expiration_date` cuando esté disponible.
- Clasifica cada dominio como:
  - `taken`
  - `available`
  - `unknown`
- Exporta resultados a JSON y CSV, y muestra salida en consola.

## Estructura principal

- `main.py`: entrypoint del script.
- `domains.json`: dominios base y TLDs a revisar.
- `config.json`: timeouts, variaciones, formato de salida y columnas.
- `modules/`: lógica modular (checks, core, reporting, config, utils).
- `output/`: resultados generados (`results.json`, `results.csv`).

## Requisitos

- Python 3.9+
- Dependencias en `requirements.txt`

Instalación rápida:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uso

Ejecución con archivos por defecto (`domains.json` y `config.json`):

```powershell
.\.venv\Scripts\python main.py
```

También puedes indicar rutas explícitas:

```powershell
.\.venv\Scripts\python main.py --domains-file domains.json --config-file config.json
```

## Configuración

### `domains.json`

```json
{
  "domains": ["datadevs", "datalab"],
  "tlds": ["com", "net", "app", "site"]
}
```

### `config.json`

Parámetros más importantes:

- `variations`: reglas de sustitución (ej. `o -> 0`, `i -> 1`).
- `timeout_seconds`: timeout por intento.
- `check_ssl`: habilita validaciones TLS.
- `output.format`: `json`, `csv` o ambos.
- `output.columns`: columnas visibles en consola/CSV y en el bloque principal del JSON.
  - Recomendado: usar `full_domain` en lugar de `domain` + `tlds`.
- `output.sort_by`: si está vacío (`[]`), respeta el orden de `domains.json` (`domains` y luego `tlds`).
- `output.console_domain_width`: ancho base de la columna `domain` en consola.
- `output.console_column_widths`: ancho por columna para consola.

## Salidas

- `output/results.csv`
  - Solo columnas configuradas en `output.columns`.
- `output/results.json`
  - Incluye columnas configuradas + secciones técnicas completas:
    - `dns`
    - `http`
    - `tls`
    - `errors`

## **Versionado y relectura de resultados**

- Al ejecutar una búsqueda completa, el programa crea una subcarpeta dentro de `output/` con la fecha y hora de ejecución en formato compacto ISO: `YYYY-MM-DD_HH-MM-SS`.
- Dentro de esa carpeta se guardan los archivos:
  - `results.csv` (CSV con las columnas configuradas)
  - `results.json` (JSON con la información completa)
  - `domains.json` (copia exacta del archivo de entrada usado en esa ejecución)
- Esto evita sobrescribir búsquedas anteriores y permite conservar historiales.

### Opciones nuevas

- `--output-folder <NOMBRE>`: indica una subcarpeta dentro de `output/` a usar. Si no se especifica, el programa crea una carpeta con timestamp.
- `--show-results`: modo lectura — muestra en consola el `results.csv` de la carpeta indicada con `--output-folder`.

Comportamiento y validaciones:
- Si `output/` no existe, se crea automáticamente.
- `--show-results` requiere que indique `--output-folder` con el nombre de la subcarpeta a mostrar.
- Si la carpeta o `results.csv` no existen, el programa mostrará un mensaje de error claro.
- Si `results.csv` está corrupto o no puede leerse, se muestra un error explicativo.

La visualización en consola usa `rich` si está disponible para mostrar una tabla coloreada; si no, hace un fallback a una tabla de texto simple.

### Ejemplos

Ejecutar una búsqueda normal (crea carpeta con timestamp):

```powershell
.\.venv\Scripts\python main.py
```

Ejecutar y forzar una carpeta de salida (útil para reproducir o sobrescribir manualmente):

```powershell
.\.venv\Scripts\python main.py --output-folder my_manual_run
```

Mostrar resultados de una ejecución previa en `output/test_run`:

```powershell
.\.venv\Scripts\python main.py --show-results --output-folder test_run
```

Si desea la presentación en colores, instale `rich`:

```powershell
pip install rich
```


## Notas

- `expiration_date`, `registrar_name` y `registrar_url` dependen de lo que exponga RDAP para cada TLD/registrar.
- Si un registro RDAP no publica ciertos datos, esos campos pueden venir vacíos.
