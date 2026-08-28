import assert from 'node:assert/strict'
import { test } from 'node:test'

import { buildSeries, summarize, toUtcDate } from './aggregate.js'

const quarters = [10, 20, 30, 40].map((price_eur, i) => ({
  timestamp_utc: `2026-08-01T00:${String(i * 15).padStart(2, '0')}:00`,
  price_eur,
}))

test('un timestamp sin offset se interpreta como UTC', () => {
  assert.equal(toUtcDate('2026-08-01T00:00:00').toISOString(), '2026-08-01T00:00:00.000Z')
  assert.equal(toUtcDate('2026-08-01T00:00:00Z').toISOString(), '2026-08-01T00:00:00.000Z')
})

test('modo horario: promedia PT15M y lo alinea con PT60M', () => {
  const rows = buildSeries(
    { ES: quarters, DE: [{ timestamp_utc: '2026-08-01T00:00:00', price_eur: 50 }] },
    true,
  )
  assert.deepEqual(rows, [{ t: Date.UTC(2026, 7, 1), ES: 25, DE: 50 }])
})

test('modo nativo: conserva los 4 puntos y deja hueco donde DE no publica', () => {
  const rows = buildSeries(
    { ES: quarters, DE: [{ timestamp_utc: '2026-08-01T00:00:00', price_eur: 50 }] },
    false,
  )
  assert.equal(rows.length, 4)
  assert.equal(rows[0].DE, 50)
  assert.equal(rows[1].DE, undefined)
  assert.deepEqual(rows.map((r) => r.ES), [10, 20, 30, 40])
})

test('summarize', () => {
  assert.deepEqual(summarize(quarters), { n: 4, min: 10, max: 40, avg: 25 })
  assert.equal(summarize([]), null)
})
