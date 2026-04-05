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
