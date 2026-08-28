# Frontend

SPA de React + Vite que consume la API REST (`backend/`) y compara precios day-ahead de ES, RO,
DE y PL. Todo se muestra en EUR/MWh y con timestamps en UTC.

## Ejecutar en local

```bash
cp .env.example .env         # apunta a tu API y pon la misma API key del backend
npm install
npm run dev                  # http://localhost:5173
```

| Variable | Qué es |
|---|---|
| `VITE_API_BASE_URL` | Base de la API. Por defecto `http://localhost:8000`. |
| `VITE_API_KEY` | Se envía en la cabecera `X-API-Key` en cada petición. |

El backend debe incluir el origen del frontend en `ALLOWED_ORIGINS`.

Otros comandos: `npm test` (node:test, sin framework), `npm run lint`, `npm run build`.

## Qué hace

- **Filtros**: países (multi-selección) y rango de fechas con `<input type="date">` nativo.
- **Comparativa multi-país**: una línea por país sobre el mismo eje temporal.
- **Tabla resumen**: registros, mínimo, media y máximo por país sobre los datos *nativos*
  (sin promediar), que es la cifra correcta para comparar contra la fuente.

## Granularidad PT15M vs PT60M

ES, RO y PL publican cada 15 min, DE cada hora. El selector de granularidad cubre los dos casos:

- **Media horaria** (por defecto): los cuatro puntos de cada hora se promedian, así todas las
  series caen en el mismo instante y la comparación es de manzanas con manzanas.
- **Nativa**: cada país a su resolución de origen. La serie alemana queda visiblemente más suave
  porque tiene 4× menos puntos. Se dibuja con `connectNulls` — sin eso sus puntos quedarían
  aislados entre los huecos de la rejilla de 15 min y la línea no se vería.

La lógica vive en [`src/aggregate.js`](src/aggregate.js), separada de la UI y cubierta por
`src/aggregate.test.js`.

