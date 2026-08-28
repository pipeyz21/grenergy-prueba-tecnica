import struct
from datetime import date

from azure.identity import ClientSecretCredential, DefaultAzureCredential

from .config import Settings, get_settings

SQL_COPT_SS_ACCESS_TOKEN = 1256
_TOKEN_SCOPE = "https://database.windows.net/.default"


def _select_credential(settings: Settings):
    if settings.azure_client_id and settings.azure_client_secret and settings.azure_tenant_id:
        return ClientSecretCredential(
            settings.azure_tenant_id, settings.azure_client_id, settings.azure_client_secret
        )
    return DefaultAzureCredential()


def _build_token_struct(access_token: str) -> bytes:
    token_bytes = access_token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def get_connection():
    # importado aquí y no arriba: con DATA_SOURCE=local/demo no hace falta
    # ni pyodbc ni el driver ODBC nativo, y así el backend despliega en cualquier host Python.
    import pyodbc

    settings = get_settings()
    credential = _select_credential(settings)
    token = credential.get_token(_TOKEN_SCOPE)
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={settings.fabric_sql_endpoint},1433;"
        f"Database={settings.fabric_database};"
        "Encrypt=yes;"
    )
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: _build_token_struct(token.token)})


def query_prices(table: str, date_from: date, date_to: date) -> list[dict]:
    """Precios en [date_from, date_to), ordenados. `table` sale solo de nuestra propia
    config (etl/config/sources.json), nunca de input de usuario."""
    sql = (
        f"SELECT timestamp_utc, price_eur FROM {table} "
        "WHERE timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, date_from, date_to).fetchall()
    return [{"timestamp_utc": ts.isoformat(), "price_eur": price} for ts, price in rows]


def _demo():
    token_struct = _build_token_struct("fake-token")
    assert len(token_struct) == 4 + len("fake-token".encode("utf-16-le"))

    class FakeSettings:
        azure_client_id = azure_client_secret = azure_tenant_id = ""

    assert isinstance(_select_credential(FakeSettings()), DefaultAzureCredential)
    print("fabric.py self-check OK")


if __name__ == "__main__":
    _demo()
