# Precios Day-Ahead — ES · RO · DE · PL

Prueba técnica Data & AI engineer (Grenergy). Ingesta diaria de precios mayoristas de
electricidad de cuatro mercados europeos a un lakehouse de Microsoft Fabric, expuestos por una
API REST propia y una interfaz web comparativa.

```
APIs (ENTSO-E, SMARD, PSE) → Pipeline Fabric → Lakehouse (raw.prices_*) → FastAPI → React
```

| Parte | Dónde | Detalle |
|---|---|---|
| Fase 1 · ETL | [`etl/`](etl/) | Pipeline + notebooks de Fabric, versionados. [README](etl/README.md) |
| Fase 2 · API | [`backend/`](backend/) | FastAPI sobre el SQL endpoint del lakehouse. |
| Fase 2 · Web | [`frontend/`](frontend/) | React + Vite. [README](frontend/README.md) |

**Interfaz desplegada:** no se publica. El SQL endpoint de Fabric solo acepta tokens de Entra,
así que un backend desplegado necesitaría un service principal, y la cuenta de la capacidad
Trial no permite registrar aplicaciones. La solución se ejecuta en local contra los datos
reales del lakehouse; ver más abajo.

## Ejecutar en local

**1. Configuración.** La misma clave en los dos ficheros: `API_KEY` en el backend y
`VITE_API_KEY` en el frontend.

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

**2. Datos.** El backend lee de una de tres fuentes según `DATA_SOURCE`
([detalle](backend/README.md#fuentes-de-datos-data_source)):

| `DATA_SOURCE` | Datos | Requiere |
|---|---|---|
| `local` | Reales, del lakehouse | Descargar los CSV a `backend/.data/` — [cómo](backend/README.md#conseguir-los-datos-sin-credenciales) |
| `fabric` | Reales, en vivo | Credenciales de Entra (`az login`, o service principal en servidor) |
| `demo` | Sintéticos | Nada. Solo para desarrollar la interfaz |

**Para reproducir sin credenciales, usa `local`**: descarga las tablas desde el portal de Fabric y
déjalas en `backend/.data/`. Es la ruta recomendada, y la única que no depende de permisos sobre el
tenant.

**3. Levantar.**

```bash
docker compose --env-file frontend/.env up --build    # API :8000 · web :8080
```

El `--env-file` no es opcional: Vite hornea las `VITE_*` en el bundle al compilar, así que compose
las necesita como *build args*. Sin él, el build aborta con un mensaje que lo indica.

Alternativa sin Docker, en dos terminales:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev    # http://localhost:5173
```

Comprobaciones: `python test_api.py` en `backend/` y `npm test` en `frontend/`.

La ETL no se ejecuta desde aquí: vive en Fabric. `etl/` versiona los notebooks, la pipeline
exportada y `config/sources.json`, que se sube a `Files/sources.json` del lakehouse. El token de
ENTSO-E se pasa como parámetro `entsoe_token` de la pipeline, no está en el repo.

## Decisiones técnicas

**Un solo notebook, configuración por fuente.** `sources.json` describe cada país (endpoint,
auth, parser, zona horaria, moneda, resolución, tabla destino). La pipeline itera las fuentes con
`active: true` en un ForEach y llama al mismo notebook. Añadir un país es una entrada en el JSON,
no código nuevo — mientras reutilice un `fetcher`/`parser` existente; una fuente con un formato
distinto añade una rama al parser, y ese es el límite honesto del diseño.

**Diferencias entre APIs, absorbidas en el parser.** Tres ejes: formato (XML de ENTSO-E vs JSON
de SMARD y PSE), acceso (SMARD obliga a leer primero un índice de bloques semanales para
resolver la URL del fichero) y granularidad (PT15M vs PT60M). ENTSO-E usa `curveType A03`, que
omite los puntos repetidos: el parser rellena las posiciones ausentes con el último precio, o
faltarían registros. También descarta las series que no son day-ahead (`A01`).

**Todo a UTC en la ingesta.** Las tres APIs entregan instantes absolutos en formatos distintos
(intervalos UTC en ENTSO-E, epoch en milisegundos en SMARD, `dtime_utc` en PSE); cada parser los
devuelve como datetime *tz-aware* en UTC, así que `timestamp_utc` nunca depende de la zona local
del runtime. Por eso los cambios de hora no generan huecos ni duplicados y la comparación entre
países es directa.

**Incremental sin huecos.** `MERGE` sobre `(timestamp_utc, country_code)` en tablas Delta
separadas por país. Cada ejecución reprocesa `lookback_days: 2`, porque los operadores publican
correcciones a posteriori: reingerir es idempotente y actualiza en vez de duplicar. Cada
ejecución deja una fila en `control.run_log`; un `success` con `rows_loaded = 0` es un fallo
silencioso y se detecta ahí.

**PLN→EUR en la ingesta, no en la lectura.** Polonia se convierte con la tabla A del NBP del día
correspondiente, retrocediendo hasta 5 días si no hay publicación (fines de semana y festivos).
Se convierte al escribir para que la columna `price_eur` sea el único precio almacenado: las
consultas no dependen de una API de FX, y el valor queda congelado al tipo del día del precio,
que es lo correcto para una serie histórica.

**Seguridad: API key en cabecera.** `X-API-Key` validada en cada endpoint, más CORS restringido a
los orígenes configurados. Es la opción proporcionada al caso: datos públicos de mercado, sin
usuarios ni roles, y sin infraestructura de identidad que justifique OAuth. Sus límites son
reales: la key viaja en el bundle del frontend (`VITE_*`) y es compartida, así que en producción
esto sería autenticación de usuario (OIDC/JWT) con el frontend como cliente público. Contra
Fabric el backend se autentica con service principal o `DefaultAzureCredential`, nunca con la key
del cliente.

**El nombre de tabla nunca viene del usuario.** El endpoint recibe un `country_code`, que se
resuelve contra `sources.json` — el mismo fichero que usa la ETL, una única fuente de verdad. La
tabla se interpola en el SQL, pero solo desde esa config; fechas y filtros van parametrizados.

**Granularidad, resuelta en el frontend.** La API devuelve cada país a su resolución nativa y su
`resolution_minutes`. La interfaz ofrece media horaria (alinea PT15M con el PT60M alemán, que es
la comparación honesta) o resolución nativa. Agregar en el cliente y no en la API mantiene el
backend como una capa fina de lectura.
