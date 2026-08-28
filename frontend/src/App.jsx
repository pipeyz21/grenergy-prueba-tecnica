import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import './App.css'
import { buildSeries, summarize } from './aggregate.js'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

const COLORS = { ES: '#e4572e', RO: '#2e6e9e', DE: '#e8a33d', PL: '#4c8577' }
const FALLBACK_COLOR = '#8884d8'

const isoDay = (ms) => new Date(ms).toISOString().slice(0, 10)
const eur = (v) => `${v.toFixed(2)} €`

async function api(path, params) {
  const url = new URL(path, API_BASE)
  for (const [k, v] of Object.entries(params ?? {})) url.searchParams.set(k, v)
  const res = await fetch(url, { headers: { 'X-API-Key': API_KEY } })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${(await res.text()).slice(0, 200)}`)
  return res.json()
}

export default function App() {
  const [countries, setCountries] = useState([])
  const [selected, setSelected] = useState([])
  const [dateFrom, setDateFrom] = useState(() => isoDay(Date.now() - 6 * 864e5))
  const [dateTo, setDateTo] = useState(() => isoDay(Date.now()))
  const [hourly, setHourly] = useState(true)
  const [byCountry, setByCountry] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api('/countries')
      .then((list) => {
        setCountries(list)
        setSelected(list.map((c) => c.country_code))
      })
      .catch((e) => setError(e.message))
  }, [])

  const load = useCallback(async () => {
    if (!selected.length) return setByCountry({})
    setLoading(true)
    setError(null)
    try {
      const responses = await Promise.all(
        selected.map((country) => api('/prices', { country, date_from: dateFrom, date_to: dateTo })),
      )
      setByCountry(Object.fromEntries(responses.map((r) => [r.country_code, r.records])))
    } catch (e) {
      setError(e.message)
      setByCountry({})
    } finally {
      setLoading(false)
    }
  }, [selected, dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  const rows = useMemo(() => buildSeries(byCountry, hourly), [byCountry, hourly])
  const stats = useMemo(
    () => Object.entries(byCountry).map(([code, records]) => ({ code, ...summarize(records) })),
    [byCountry],
  )

  const toggle = (code) =>
    setSelected((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]))

  const meta = (code) => countries.find((c) => c.country_code === code) ?? {}
  const color = (code) => COLORS[code] ?? FALLBACK_COLOR

  return (
    <main>
      <header>
        <h1>Precios Day-Ahead</h1>
        <p>Mercados eléctricos europeos · todo en EUR/MWh · timestamps en UTC</p>
      </header>

      <section className="controls">
        <fieldset>
          <legend>Países</legend>
          <div className="chips">
            {countries.map((c) => (
              <label key={c.country_code} className={selected.includes(c.country_code) ? 'chip on' : 'chip'}>
                <input
                  type="checkbox"
                  checked={selected.includes(c.country_code)}
                  onChange={() => toggle(c.country_code)}
                />
                <span className="dot" style={{ background: color(c.country_code) }} />
                {c.country_name} <small>PT{c.resolution_minutes}M</small>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>Rango</legend>
          <label>Desde <input type="date" value={dateFrom} max={dateTo} onChange={(e) => setDateFrom(e.target.value)} /></label>
          <label>Hasta <input type="date" value={dateTo} min={dateFrom} onChange={(e) => setDateTo(e.target.value)} /></label>
        </fieldset>

        <fieldset>
          <legend>Granularidad</legend>
          <label><input type="radio" checked={hourly} onChange={() => setHourly(true)} /> Media horaria</label>
          <label><input type="radio" checked={!hourly} onChange={() => setHourly(false)} /> Nativa</label>
          <small>
            {hourly
              ? 'PT15M promediado a hora, comparable con el PT60M de Alemania.'
              : 'Resolución de cada fuente (Alemania solo publica en punto)'}
          </small>
        </fieldset>
      </section>

      {error && <p className="error">No se pudieron cargar los datos: {error}</p>}
      {loading && <p className="muted">Cargando…</p>}
      {!loading && !error && !rows.length && <p className="muted">Sin datos para esta selección.</p>}

      {!!rows.length && (
        <section className="chart">
          <ResponsiveContainer width="100%" height={420}>
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e6e6e6" />
              <XAxis
                dataKey="t"
                type="number"
                scale="time"
                domain={['dataMin', 'dataMax']}
                tickFormatter={(t) => new Date(t).toISOString().slice(5, 16).replace('T', ' ')}
                minTickGap={48}
              />
              <YAxis unit=" €" width={70} />
              <Tooltip
                labelFormatter={(t) => `${new Date(t).toISOString().slice(0, 16).replace('T', ' ')} UTC`}
                formatter={(v, code) => [eur(v), meta(code).country_name ?? code]}
              />
              <Legend formatter={(code) => meta(code).country_name ?? code} />
              {selected.map((code) => (
                <Line
                  key={code}
                  type="monotone"
                  dataKey={code}
                  stroke={color(code)}
                  dot={false}
                  strokeWidth={2}
                  connectNulls  /* en modo nativo DE solo tiene puntos en punto: sin esto su línea no se dibuja */
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}

      {!!stats.length && (
        <table>
          <caption>Resumen del rango seleccionado (sobre los datos nativos, sin promediar)</caption>
          <thead>
            <tr><th>País</th><th>Resolución</th><th>Registros</th><th>Mínimo</th><th>Media</th><th>Máximo</th></tr>
          </thead>
          <tbody>
            {stats.map((s) => (
              <tr key={s.code}>
                <td><span className="dot" style={{ background: color(s.code) }} /> {meta(s.code).country_name ?? s.code}</td>
                <td>PT{meta(s.code).resolution_minutes}M</td>
                <td>{s.n ?? 0}</td>
                <td>{s.min == null ? '—' : eur(s.min)}</td>
                <td>{s.avg == null ? '—' : eur(s.avg)}</td>
                <td>{s.max == null ? '—' : eur(s.max)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}
