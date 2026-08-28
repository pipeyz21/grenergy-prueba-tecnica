# ETL — Precios day-ahead

Ingesta diaria de precios mayoristas de electricidad de ES, RO, DE y PL a un lakehouse de Fabric.
Esta carpeta versiona lo que vive en Fabric, no se ejecuta desde aquí.

## Contenido

| Fichero | Qué es |
|---|---|
| `notebooks/nb_ingest.ipynb` | Notebook genérico de ingesta. |
| `notebooks/nb_setup.ipynb` | Notebook de creación de tablas de logs. |
| `notebooks/nb_get_config.ipynb` | Notebook que obtiene la configuración desde el lakehouse |
| `config/sources.json` | Definición de las 4 fuentes. Se sube a `Files/sources.json` del lakehouse. |
| `plp_generic_ingest.json` | Export de la pipeline. |

## Cómo corre

La pipeline lee `sources.json`, itera las fuentes con `active: true` en un ForEach y llama al
notebook con dos *base parameters* (ambos string):

| Parámetro | Valor |
|---|---|
| `source_json` | `@string(item())` — la fuente serializada |
| `api_token` | `@pipeline().parameters.entsoe_token` |

La celda 0 del notebook tiene que estar marcada como **parameter cell**,
o sus valores por defecto pisan lo que inyecta la pipeline.

El notebook extrae, parsea, convierte a EUR y hace `MERGE` sobre la tabla destino, que crea en la
primera ejecución. Cada ejecución deja una fila en `control.run_log` (`status`, `rows_loaded`,
`error_message`). Un `success` con `rows_loaded = 0` es un fallo silencioso.

## Fuentes

| País | Origen | Auth | Granularidad | Tabla |
|---|---|---|---|---|
| ES | ENTSO-E `A44` | token | 15 min | `raw.prices_es` |
| RO | ENTSO-E `A44` | token | 15 min | `raw.prices_ro` |
| DE | SMARD | no | 60 min | `raw.prices_de` |
| PL | PSE `rce-pln` | no | 15 min | `raw.prices_pl` |

Todas las tablas: `timestamp_utc`, `price_eur`, `country_code`, `source_id`, `ingested_at`.
Clave de deduplicación y de `MERGE`: `(timestamp_utc, country_code)`.

`ingestion.lookback_days: 2` reprocesa los 2 días anteriores en cada ejecución, para recoger las
correcciones que publican los operadores.
