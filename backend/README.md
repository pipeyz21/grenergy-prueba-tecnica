# Backend — API REST de precios day-ahead

FastAPI sobre el SQL endpoint del lakehouse de Fabric. Expone las tablas de la Fase 1
(`raw.prices_es|ro|de|pl`) para que el frontend las grafique y compare.

## Endpoints

| Método | Ruta | Auth | Qué devuelve |
|---|---|---|---|
| `GET` | `/health` | no | `{"status":"ok"}` — liveness, sin tocar Fabric. |
| `GET` | `/countries` | sí | Países activos con moneda, unidad y `resolution_minutes`. |
| `GET` | `/prices?country=ES&date_from=2026-08-01&date_to=2026-08-07` | sí | Serie de precios. |

`date_from` y `date_to` son días **inclusivos** (`YYYY-MM-DD`); internamente se consulta el
intervalo semiabierto `[date_from, date_to + 1 día)` sobre `timestamp_utc`.

```json
{
  "country_code": "PL",
  "currency": "EUR",
  "unit": "EUR/MWh",
  "resolution_minutes": 15,
  "records": [{"timestamp_utc": "2026-08-01T00:00:00", "price_eur": 84.12}]
}
```

Docs interactivas en `/docs`.

## Fuentes de datos (`DATA_SOURCE`)

El backend lee los precios de una de tres fuentes. La respuesta de `/prices` incluye
`data_source`, para que nunca haya duda de qué se está mirando.

| Valor | De dónde | Credenciales | Cuándo |
|---|---|---|---|
| `fabric` (def.) | Lakehouse en vivo | Entra: `az login` en local, service principal en servidor | Datos al día. |
| `local` | CSV en `backend/.data/` | ninguna | Trabajar y desplegar sin secretos. Datos reales, congelados. |
| `demo` | Sintéticos | ninguna | Desarrollar la interfaz. **No son precios reales.** |

`local` y `demo` no importan `pyodbc` (el import es perezoso en `fabric.py`), así que en esos
modos el backend corre en cualquier host Python sin driver ODBC.

### Conseguir los datos sin credenciales

Los CSV están en el repo, pero estan desactualizados, hay que descargarlos del lakehouse. Ejecuta esto en un notebook de
Fabric con el lakehouse adjunto:

```python
df = spark.sql("""
    SELECT * FROM raw.prices_es
    UNION ALL SELECT * FROM raw.prices_ro
    UNION ALL SELECT * FROM raw.prices_de
    UNION ALL SELECT * FROM raw.prices_pl
""").toPandas()

notebookutils.fs.put("Files/data.csv", df.to_csv(index=False), True)
```

Luego, en el explorador del lakehouse: **Files → `data.csv` → Download**, y lo dejas en
`backend/.data/`. Solo hace falta la sesión de navegador con la que corres la ETL: ni Azure CLI, ni
service principal, ni acceso al portal de Entra.

> **No uses el botón de descarga de la vista previa de la tabla:** corta a 1000 filas sin avisar,
> y el recorte no se reparte por igual entre países. `notebookutils.fs.put` escribe el resultado
> completo.
>
> Si prefieres escribir con pandas directamente, la ruta es `/lakehouse/default/Files/data.csv`
> — el punto de montaje del lakehouse adjunto, no `/<nombre_del_lakehouse>/Files/`.

Se leen todos los `*.csv` del directorio, así que da igual un fichero por país o uno único. El país
sale de la columna `country_code`; si el CSV no la trae, del nombre del fichero (`prices_es.csv` →
ES). Los timestamps se normalizan a UTC sin offset, que es lo que espera el frontend, y `/prices`
devuelve `data_as_of` con la fecha de descarga.

## Ejecutar

```bash
cp .env.example .env   # rellenar FABRIC_SQL_ENDPOINT, FABRIC_DATABASE y API_KEY
```

Con Docker (trae el driver ODBC 18 ya instalado — recomendado):

```bash
docker compose up --build backend
```

En local hace falta el driver de Microsoft (`brew install msodbcsql18`) y credenciales de Azure
(`az login`, o service principal en el `.env`):

```bash
pip install -r requirements.txt && uvicorn app.main:app --reload
```

El build de la imagen usa la **raíz del repo** como contexto, porque copia
`etl/config/sources.json` dentro: es la misma config que consume la pipeline de Fabric.

### Check

```bash
pip install httpx && API_KEY=test-key python test_api.py
```

Cubre auth, validación de parámetros y las tres fuentes de datos, sin conexión a Fabric.