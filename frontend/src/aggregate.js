export const HOUR_MS = 3_600_000

/** La API serializa datetimes naive ("2026-08-01T00:00:00"); sin la Z, JS los leería como hora local. */
export function toUtcDate(iso) {
  return new Date(/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`)
}

/**
 * { ES: [{timestamp_utc, price_eur}], ... } -> [{ t, ES, DE, ... }] ordenado por t.
 * hourly=true promedia cada hora, que es lo que alinea PT15M (ES/RO/PL) con PT60M (DE).
 * hourly=false respeta la resolución nativa: DE deja huecos en :15/:30/:45, y eso se ve.
 */
export function buildSeries(byCountry, hourly) {
  const grid = new Map()
  for (const [code, records] of Object.entries(byCountry)) {
    const buckets = new Map()
    for (const r of records) {
      const t = toUtcDate(r.timestamp_utc).getTime()
      const key = hourly ? t - (t % HOUR_MS) : t
      const b = buckets.get(key) ?? { sum: 0, n: 0 }
      b.sum += r.price_eur
      b.n += 1
      buckets.set(key, b)
    }
    for (const [key, b] of buckets) {
      const row = grid.get(key) ?? { t: key }
      row[code] = b.sum / b.n
      grid.set(key, row)
    }
  }
  return [...grid.values()].sort((a, b) => a.t - b.t)
}

export function summarize(records) {
  if (!records?.length) return null
  let min = Infinity
  let max = -Infinity
  let sum = 0
  for (const { price_eur: p } of records) {
    if (p < min) min = p
    if (p > max) max = p
    sum += p
  }
  return { n: records.length, min, max, avg: sum / records.length }
}
