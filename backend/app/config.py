import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

DEFAULT_SOURCES_PATH = Path(__file__).resolve().parent.parent.parent / "etl" / "config" / "sources.json"


class Settings(BaseSettings):
    api_key: str = "dev-local-key"
    allowed_origins: str = "*"

    # De dónde salen los precios: "fabric" (live), "local" (CSV descargados) o "demo" (sintéticos).
    data_source: str = "fabric"
    data_dir: str = str(Path(__file__).resolve().parent.parent / ".data")

    fabric_sql_endpoint: str = ""  
    fabric_database: str = ""
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    sources_config_path: str = str(DEFAULT_SOURCES_PATH)

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_country_tables() -> dict[str, dict]:
    """country_code -> metadata, sourced from the ETL config (single source of truth).

    La ETL ya convierte todo a EUR antes de escribir (columna `price_eur`), así que la moneda
    expuesta es siempre EUR; `source_currency` conserva la original solo como información.
    """
    path = Path(get_settings().sources_config_path)
    sources = json.loads(path.read_text())
    return {
        s["country_code"]: {
            "country_name": s["country_name"],
            "table": s["target_table"],
            "currency": "EUR",
            "unit": "EUR/MWh",
            "source_currency": s["currency"],
            "resolution_minutes": s["resolution_minutes"],
        }
        for s in sources
        if s.get("active", True)
    }
