"""Sirve los CSV descargados a mano del lakehouse, para trabajar sin credenciales de Entra.

Son datos REALES, congelados en el momento de la descarga. Lee todos los `*.csv` de `.data/`,
así da igual bajar una tabla por país o un export único: el país sale de la columna
`country_code` y, si el CSV no la trae, del nombre del fichero (`prices_es.csv` -> ES).
"""
import csv
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

from .config import get_settings

_CODE_LEN = 2


def _normalize_ts(value: str) -> str:
    """'2026-08-01 00:00:00.000Z' / '2026-08-01T00:00:00+00:00' -> '2026-08-01T00:00:00' (UTC)."""
    v = value.strip().replace(" ", "T")
    if v.endswith("Z"):
        v = v[:-1]
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat()


def _country_from_name(path: Path) -> str:
    """`prices_es.csv`, `raw.prices_es.csv`, `ES.csv` -> 'ES'."""
    code = path.stem.split(".")[-1].split("_")[-1]
    return code.upper() if len(code) == _CODE_LEN else ""


@lru_cache
def _load() -> tuple[dict[str, list[dict]], str | None]:
    data_dir = Path(get_settings().data_dir)
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"DATA_SOURCE=local pero no hay ningún .csv en {data_dir}. "
            "Descarga las tablas del lakehouse desde el portal de Fabric y déjalas ahí."
        )

    by_country: dict[str, list[dict]] = {}
    for path in files:
        fallback = _country_from_name(path)
        with path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                country = (row.get("country_code") or fallback).strip().upper()
                if not country:
                    raise ValueError(
                        f"{path.name}: sin columna 'country_code' y el nombre del fichero no dice "
                        "el país. Renómbralo a algo como 'prices_es.csv'."
                    )
                by_country.setdefault(country, []).append({
                    "timestamp_utc": _normalize_ts(row["timestamp_utc"]),
                    "price_eur": float(row["price_eur"]),
                })

    for records in by_country.values():
        records.sort(key=lambda r: r["timestamp_utc"])

    downloaded_at = datetime.fromtimestamp(
        max(f.stat().st_mtime for f in files), tz=timezone.utc
    ).replace(microsecond=0).isoformat()
    return by_country, downloaded_at


def downloaded_at() -> str | None:
    return _load()[1]


def read(country: str, date_from: date, date_to: date) -> list[dict]:
    """Precios en [date_from, date_to)."""
    lo, hi = date_from.isoformat(), date_to.isoformat()
    return [r for r in _load()[0].get(country, []) if lo <= r["timestamp_utc"][:10] < hi]
