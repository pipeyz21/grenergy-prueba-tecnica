"""Datos sintéticos para desarrollar el frontend sin conexión a Fabric.

NO son precios reales: es una curva plausible (valle nocturno, pico de mañana y de tarde) para
poder probar filtros, comparativa y el manejo de granularidades. Se activa con DEMO_MODE=true y
la respuesta de /prices lo marca con `"demo": true` para que no se confunda con datos de verdad.
"""
import math
import random
from datetime import date, datetime, timedelta

# Nivel medio €/MWh por país, para que la comparativa multi-país no salga con 4 curvas idénticas.
_BASE = {"ES": 78.0, "RO": 92.0, "DE": 71.0, "PL": 85.0}


def _shape(hour: float) -> float:
    """Perfil intradiario normalizado: valle sobre las 4h, picos sobre las 9h y las 20h."""
    return 0.55 * math.sin((hour - 9) * math.pi / 12) + 0.45 * math.sin((hour - 20) * math.pi / 6)


def generate(country: str, resolution_minutes: int, date_from: date, date_to: date) -> list[dict]:
    """Serie en [date_from, date_to), al paso nativo del país (15 o 60 min)."""
    base = _BASE.get(country, 80.0)
    step = timedelta(minutes=resolution_minutes)
    records = []
    t = datetime.combine(date_from, datetime.min.time())
    end = datetime.combine(date_to, datetime.min.time())
    while t < end:
        # semilla determinista: el mismo rango devuelve siempre la misma serie
        rng = random.Random(f"{country}-{t.isoformat()}")
        hour = t.hour + t.minute / 60
        price = base * (1 + 0.35 * _shape(hour)) + rng.uniform(-4, 4)
        records.append({"timestamp_utc": t.isoformat(), "price_eur": round(price, 2)})
        t += step
    return records


def _demo():
    rows = generate("ES", 15, date(2026, 8, 1), date(2026, 8, 2))
    assert len(rows) == 96, len(rows)
    assert len(generate("DE", 60, date(2026, 8, 1), date(2026, 8, 2))) == 24
    assert rows == generate("ES", 15, date(2026, 8, 1), date(2026, 8, 2)), "no determinista"
    assert all(0 < r["price_eur"] < 300 for r in rows), "precios fuera de rango plausible"
    # el valle nocturno tiene que estar por debajo del pico de tarde
    noche = next(r for r in rows if r["timestamp_utc"].endswith("T04:00:00"))
    tarde = next(r for r in rows if r["timestamp_utc"].endswith("T20:00:00"))
    assert noche["price_eur"] < tarde["price_eur"]
    print("demo.py self-check OK")


if __name__ == "__main__":
    _demo()
