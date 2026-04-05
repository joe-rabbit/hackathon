# InfluxDB Dashboard Queries (Carbon Metrics)

Bucket assumed: `metrics`

## 1) Latest Total Energy (kWh)

Visualization: Single Stat

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kwh")
  |> last()
```

## 2) Latest Total CO2e (kg)

Visualization: Single Stat

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> last()
```

## 3) Energy Over Time

Visualization: Line

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kwh")
  |> aggregateWindow(every: 5m, fn: last, createEmpty: false)
```

## 4) CO2e Over Time

Visualization: Line

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> aggregateWindow(every: 5m, fn: last, createEmpty: false)
```

## 5) Incremental Energy per Snapshot

Visualization: Bar

```flux
base = from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kwh")
  |> sort(columns: ["_time"])

base
  |> difference(nonNegative: true)
```

## 6) Top Models by CO2e (Latest)

Visualization: Bar

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_model_totals" and r._field == "kg_co2e")
  |> group(columns: ["model"])
  |> last()
  |> sort(columns: ["_value"], desc: true)
  |> limit(n: 10)
```

## 7) Top Models by Energy (kWh, Latest)

Visualization: Bar

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_model_totals" and r._field == "kwh_estimate")
  |> group(columns: ["model"])
  |> last()
  |> sort(columns: ["_value"], desc: true)
  |> limit(n: 10)
```

## 8) Usage by source (Copilot vs Claude)

Visualization: Bar or Table

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "ai_usage_totals" and r._field == "total_tokens")
  |> group(columns: ["source"])
  |> last()
```

## 9) Prompt efficiency ratio (compressed / original)

Visualization: Gauge or Single Stat (latest)

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_optimization" and r._field == "efficiency_ratio")
  |> last()
```

## 10) g CO₂ saved by prompt compression (latest snapshot)

Visualization: Single Stat

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_optimization" and r._field == "carbon_saved_g")
  |> last()
```

## 11) Tokens saved over time (prompt-level optimization)

Visualization: Line

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_optimization" and r._field == "tokens_saved")
  |> aggregateWindow(every: 5m, fn: last, createEmpty: false)
```

## 12) Equivalent miles driven (from cumulative kg CO₂e — adjust multiplier in panel)

Use **Script** or **custom cell**: multiply `kg_co2e` from `copilot_totals` by 1000 → g, then divide by ~400 g/mile. Or add a Transform in Grafana-style UI if available.

Example (Flux — approximate miles from latest total CO₂e in kg):

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> last()
  |> map(fn: (r) => ({ r with _value: r._value * 1000.0 / 400.0 }))
```

Visualization: Single Stat (unit: miles equivalent)

## 13) Trees per day equivalent (order-of-magnitude offset)

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> last()
  |> map(fn: (r) => ({ r with _value: r._value * 1000.0 / 55.0 }))
```

Assumes ~55 g CO₂e / tree / day rough offset; label panel “tree-days equivalent”.

## 14) Dedup cache candidates found (latest)

Visualization: Single Stat

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_dedup" and r._field == "pairs_found")
  |> last()
```

## 15) Tokens saved if duplicates were cached (latest)

Visualization: Single Stat

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_dedup" and r._field == "tokens_saved_if_cached_total")
  |> last()
```

## 16) Prompt-efficiency tokens saved by optimization type

Visualization: Bar or Table

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "tokens_saved")
  |> group(columns: ["optimization_type"])
  |> sum()
```

## 17) Prompt-efficiency carbon saved over time

Visualization: Line

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "carbon_saved_g")
  |> aggregateWindow(every: 5m, fn: sum, createEmpty: false)
```
