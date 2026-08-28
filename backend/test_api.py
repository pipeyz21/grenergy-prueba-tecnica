"""Check mínimo de la API: auth y validación de parámetros. No toca Fabric.

    pip install httpx && API_KEY=test-key python test_api.py
"""
import importlib
import os
import pathlib

os.environ.setdefault("API_KEY", "test-key")
os.environ["DATA_SOURCE"] = "fabric"  # el .env del desarrollador no debe alterar el check

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.config import get_country_tables, get_settings  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)
h = {"X-API-Key": os.environ["API_KEY"]}

assert c.get("/health").status_code == 200
assert c.get("/countries").status_code == 401, "endpoint sin proteger"
assert c.get("/countries", headers={"X-API-Key": "nope"}).status_code == 401

countries = c.get("/countries", headers=h).json()
assert {x["country_code"] for x in countries} == {"ES", "RO", "DE", "PL"}
assert all(x["currency"] == "EUR" for x in countries), "la ETL ya escribe EUR, la API debe reflejarlo"
assert {x["country_code"]: x["resolution_minutes"] for x in countries}["DE"] == 60
assert "table" not in countries[0], "no exponer nombres de tabla internos"

assert c.get("/prices?country=ES&date_from=ayer&date_to=2026-08-20", headers=h).status_code == 422
assert c.get("/prices?country=ES&date_from=2026-08-01", headers=h).status_code == 422
assert c.get("/prices?country=XX&date_from=2026-08-01&date_to=2026-08-02", headers=h).status_code == 404
assert c.get("/prices?country=ES&date_from=2026-08-10&date_to=2026-08-01", headers=h).status_code == 422

# la columna consultada tiene que existir en las tablas que escribe la ETL
import inspect  # noqa: E402

from app import fabric  # noqa: E402

assert "timestamp_utc" in inspect.getsource(fabric.query_prices)
assert get_country_tables()["PL"]["source_currency"] == "PLN"

# --- DATA_SOURCE=demo: sintéticos, sin tocar Fabric ---
get_settings.cache_clear()
os.environ["DATA_SOURCE"] = "demo"
importlib.reload(main)
d = TestClient(main.app)

r = d.get("/prices?country=DE&date_from=2026-08-01&date_to=2026-08-02", headers=h).json()
assert r["data_source"] == "demo", "la fuente debe ir marcada en la respuesta"
assert len(r["records"]) == 48, "2 días x 24 h para DE (PT60M)"
r15 = d.get("/prices?country=ES&date_from=2026-08-01&date_to=2026-08-02", headers=h).json()
assert len(r15["records"]) == 192, "2 días x 96 cuartos para ES (PT15M)"
assert r15["currency"] == "EUR"

# --- DATA_SOURCE=local: CSV descargados del lakehouse, sin credenciales ---
import tempfile  # noqa: E402

tmp = tempfile.mkdtemp()
# una tabla sin country_code (el país sale del nombre) y otra con él (descarga directa),
# y los tres formatos de timestamp que puede soltar un export de Fabric
(pathlib.Path(tmp) / "prices_es.csv").write_text(
    "timestamp_utc,price_eur\n"
    "2026-08-01 00:00:00.000Z,50.0\n"
    "2026-08-02T00:00:00,51.0\n"
    "2026-08-03T00:00:00+00:00,52.0\n"
)
(pathlib.Path(tmp) / "cualquier_nombre.csv").write_text(
    "timestamp_utc,price_eur,country_code,source_id\n"
    "2026-08-02T00:00:00,90.0,DE,smard_de_dayahead\n"
)

get_settings.cache_clear()
os.environ["DATA_SOURCE"] = "local"
os.environ["DATA_DIR"] = tmp
importlib.reload(main)
loc = TestClient(main.app)

r = loc.get("/prices?country=ES&date_from=2026-08-01&date_to=2026-08-02", headers=h).json()
assert r["data_source"] == "local"
assert r["data_as_of"], "hay que decir de cuándo son los datos"
assert [x["price_eur"] for x in r["records"]] == [50.0, 51.0], "date_to inclusivo"
assert r["records"][0]["timestamp_utc"] == "2026-08-01T00:00:00", "el sufijo Z debe normalizarse"

# el país sale de country_code aunque el fichero se llame cualquier cosa
de = loc.get("/prices?country=DE&date_from=2026-08-02&date_to=2026-08-02", headers=h).json()
assert [x["price_eur"] for x in de["records"]] == [90.0]

# país sin datos -> lista vacía, no error
assert loc.get("/prices?country=PL&date_from=2026-08-01&date_to=2026-08-02",
               headers=h).json()["records"] == []

# DATA_SOURCE inválido tiene que petar al arrancar, no servir datos raros
os.environ["DATA_SOURCE"] = "chorizo"
get_settings.cache_clear()
try:
    importlib.reload(main)
    raise AssertionError("un DATA_SOURCE inválido debería abortar el arranque")
except ValueError:
    pass

for k in ("DATA_SOURCE", "DATA_DIR"):
    os.environ.pop(k, None)
get_settings.cache_clear()

print("test_api.py OK")
