# Domains Checker

Herramienta CLI en Python para comprobar disponibilidad de dominios y
generar variantes tipográficas. Exporta resultados en JSON y CSV y puede
mostrar tablas en la consola.

![Domains Checker](images/domains-checker-demo.png)

## Qué hace este proyecto

- Lee dominios base y TLDs desde `domains.json`.
- Genera candidatos, p. ej.: `dominio.com`, `dominio.net`.
- Genera variantes tipográficas según `config.json`.
- Ejecuta chequeos concurrentes: DNS, HTTP/HTTPS, TLS y RDAP.
- Clasifica dominios: `taken`, `available` o `unknown`.
- Exporta a `results.json` y `results.csv`.

## Estructura principal

- `main.py`: entrypoint del script.
- `domains.json`: dominios base y TLDs a revisar.
- `config.json`: timeouts, variaciones y formato de salida.
- `modules/`: lógica modular (checks, core, reporting, config, utils).
- `output/`: resultados generados.

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

Indicar archivos explícitos:

```powershell
.\.venv\Scripts\python main.py --domains-file domains.json \
  --config-file config.json
```

## Configuración

### `domains.json` (ejemplo)

```json
{
  "domains": [
    "postek",
    "postekusa",
    "postek-usa"
  ],
  "tlds": [
    "com",
    "net",
    "tech",
    "site",
    "app",
    "io",
    "org"
  ]
}
```
El repositorio incluye este listado de ejemplo para la campaña Postek, pero puedes reemplazarlo con tus propios dominios o variantes.

### Parámetros relevantes (`config.json`)

- `variation.variation_check`: activa la generación de variaciones.
- `variation.variation_list`: reglas de sustitución (ej. `a -> 4`).
- `timeout_seconds`: timeout por intento.
- `check_ssl`: habilita validaciones TLS.
- `output.format`: `json`, `csv` o ambos.
- `output.columns`: columnas visibles en CSV/consola.
- `output.sort_by`: criterio de orden.

## Salidas

- `output/results.csv`: columnas según `output.columns`.
- `output/results.json`: incluye datos técnicos (dns, http, tls).

## Versionado y relectura

Al ejecutar una búsqueda completa, el programa crea una subcarpeta en
`output/` con la fecha y hora en formato `YYYY-MM-DD_HH-MM-SS`.

Dentro de esa carpeta se guardan:

- `results.csv`
- `results.json`
- `domains.json` (copia del archivo usado en la ejecución)

## Opciones relevantes

- `--output-folder <NOMBRE>`: subcarpeta en `output/` a usar.
- `--show-results`: muestra `results.csv` de la carpeta indicada.

Comportamientos:

- Si `output/` no existe, se crea automáticamente.
- `--show-results` requiere `--output-folder`.
- Si la carpeta o `results.csv` no existen, se muestra un error claro.

La visualización en consola usa `rich` si está disponible; si no,
se muestra una tabla de texto simple.

## Ejemplos

Ejecutar y crear carpeta con timestamp:

```powershell
.\.venv\Scripts\python main.py
```

Usar carpeta forzada:

```powershell
.\.venv\Scripts\python main.py --output-folder my_manual_run
```

Leer resultados previos:

```powershell
.\.venv\Scripts\python main.py --show-results \
  --output-folder test_run
```

Instalar `rich` para colores:

```powershell
pip install rich
```

## Notas

- `expiration_date`, `registrar_name` y `registrar_url` dependen de RDAP.
- Si RDAP no publica datos, algunos campos pueden venir vacíos.
