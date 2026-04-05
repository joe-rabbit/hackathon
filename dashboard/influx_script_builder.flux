// =============================================================================
// InfluxDB 2.x — Carbon Footprint dashboard (Flux Script Builder)
// Bucket: metrics | Org: hackathon
//
// HOW TO USE
// 1. Dashboards → your dashboard → Add cell (or edit cell).
// 2. Open SCRIPT EDITOR (not only the query builder).
// 3. Copy ONE block below (from the comment through the closing of that query).
// 4. SUBMIT → pick visualization (noted per block) → name the cell → Save.
// 5. Time range (dashboard top): Past 30d is fine; use Past 1h while debugging.
//
// Each /* ... */ block = one cell. Do not paste the whole file into one cell.
// =============================================================================


// -----------------------------------------------------------------------------
// CELL 1 — Latest total energy (kWh)
// Visualization: Single Stat
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kwh")
  |> last()


// -----------------------------------------------------------------------------
// CELL 2 — Latest total CO2e (kg)
// Visualization: Single Stat
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> last()


// -----------------------------------------------------------------------------
// CELL 3 — Energy over time
// Visualization: Line
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kwh")
  |> aggregateWindow(every: 5m, fn: last, createEmpty: false)


// -----------------------------------------------------------------------------
// CELL 4 — CO2e over time
// Visualization: Line
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> aggregateWindow(every: 5m, fn: last, createEmpty: false)


// -----------------------------------------------------------------------------
// CELL 5 — Incremental energy per snapshot (delta kWh)
// Visualization: Bar
// -----------------------------------------------------------------------------
base = from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kwh")
  |> sort(columns: ["_time"])

base
  |> difference(nonNegative: true)


// -----------------------------------------------------------------------------
// CELL 6 — Top models by CO2e (latest)
// Visualization: Bar
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_model_totals" and r._field == "kg_co2e")
  |> group(columns: ["model"])
  |> last()
  |> sort(columns: ["_value"], desc: true)
  |> limit(n: 10)


// -----------------------------------------------------------------------------
// CELL 7 — Top models by energy (kWh estimate, latest)
// Visualization: Bar
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_model_totals" and r._field == "kwh_estimate")
  |> group(columns: ["model"])
  |> last()
  |> sort(columns: ["_value"], desc: true)
  |> limit(n: 10)


// -----------------------------------------------------------------------------
// CELL 8 — Usage by source (Copilot vs Claude) — requires ai_usage_totals in data
// Visualization: Bar or Table
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "ai_usage_totals" and r._field == "total_tokens")
  |> group(columns: ["source"])
  |> last()


// -----------------------------------------------------------------------------
// CELL 9 — Prompt efficiency ratio (latest)
// Visualization: Gauge or Single Stat
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_optimization" and r._field == "efficiency_ratio")
  |> last()


// -----------------------------------------------------------------------------
// CELL 10 — g CO2 saved by prompt compression (latest)
// Visualization: Single Stat
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_optimization" and r._field == "carbon_saved_g")
  |> last()


// -----------------------------------------------------------------------------
// CELL 11 — Tokens saved over time (prompt optimization)
// Visualization: Line
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_optimization" and r._field == "tokens_saved")
  |> aggregateWindow(every: 5m, fn: last, createEmpty: false)


// -----------------------------------------------------------------------------
// CELL 12 — Equivalent miles driven (rough, from latest kg CO2e)
// Visualization: Single Stat (unit: miles equivalent)
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> last()
  |> map(fn: (r) => ({ r with _value: r._value * 1000.0 / 400.0 }))


// -----------------------------------------------------------------------------
// CELL 13 — Tree-days equivalent (rough offset)
// Visualization: Single Stat
// -----------------------------------------------------------------------------
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> last()
  |> map(fn: (r) => ({ r with _value: r._value * 1000.0 / 55.0 }))
