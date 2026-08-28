import logging
from datetime import date, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import demo, local_data
from .config import get_country_tables, get_settings
from .fabric import query_prices
from .security import require_api_key

app = FastAPI(title="Grenergy Day-Ahead Prices API")

settings = get_settings()
if settings.data_source not in ("fabric", "local", "demo"):
    raise ValueError(f"DATA_SOURCE inválido: {settings.data_source!r}")
if settings.data_source == "demo":
    logging.warning("DATA_SOURCE=demo: /prices devuelve datos SINTÉTICOS, no reales.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_methods=["GET"],
    allow_headers=["X-API-Key"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/countries", dependencies=[Depends(require_api_key)])
def countries():
    """Metadatos por país. `resolution_minutes` permite al frontend alinear PT15M vs PT60M."""
    return [
        {"country_code": code, **{k: v for k, v in meta.items() if k != "table"}}
        for code, meta in get_country_tables().items()
    ]


@app.get("/prices", dependencies=[Depends(require_api_key)])
def prices(
    country: str,
    date_from: date = Query(description="Primer día incluido (YYYY-MM-DD)"),
    date_to: date = Query(description="Último día incluido (YYYY-MM-DD)"),
):
    tables = get_country_tables()
    country = country.upper()
    if country not in tables:
        raise HTTPException(status_code=404, detail=f"País desconocido '{country}'. Ver /countries")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from no puede ser posterior a date_to")

    meta = tables[country]
    date_end = date_to + timedelta(days=1)
    if settings.data_source == "demo":
        records = demo.generate(country, meta["resolution_minutes"], date_from, date_end)
    elif settings.data_source == "local":
        records = local_data.read(country, date_from, date_end)
    else:
        records = query_prices(meta["table"], date_from, date_end)
    return {
        "country_code": country,
        "data_source": settings.data_source,
        "data_as_of": local_data.downloaded_at() if settings.data_source == "local" else None,
        "currency": meta["currency"],
        "unit": meta["unit"],
        "resolution_minutes": meta["resolution_minutes"],
        "records": records,
    }
