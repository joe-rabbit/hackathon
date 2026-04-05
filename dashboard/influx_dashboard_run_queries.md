# Mochi Dashboard Run Queries by Visualization Type

Bucket: metrics  
Default range: last 30 days unless noted

## 1. Gauge: Prompt Efficiency Ratio (Latest)

Use this as a gauge from 0 to 1.

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_optimization" and r._field == "efficiency_ratio")
  |> last()
```

## 2. Single Stat: Total Carbon Saved in Last 24h (g)

```flux
from(bucket: "metrics")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "carbon_saved_g")
  |> sum()
```

## 3. Line Graph: Carbon Pulse (Incremental CO2 Change)

This avoids flat lines by plotting non-negative increments.

```flux
from(bucket: "metrics")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "copilot_totals" and r._field == "kg_co2e")
  |> aggregateWindow(every: 10m, fn: last, createEmpty: false)
  |> difference(nonNegative: true)
```

## 4. Heatmap: Carbon Saved by Hour and Optimization Type

Use this 2-column output for tools that require explicit X and Y columns.
X = `hour_of_day`, Y = `carbon_saved_g`.

```flux
import "date"

from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "carbon_saved_g")
  |> map(fn: (r) => ({ hour_of_day: date.hour(t: r._time), carbon_saved_g: float(v: r._value) }))
  |> group(columns: ["hour_of_day"])
  |> sum(column: "carbon_saved_g")
  |> keep(columns: ["hour_of_day", "carbon_saved_g"])
  |> sort(columns: ["hour_of_day"])
```

## 5. Mosaic (Treemap): Token Savings Share by Type and Task

If your UI has no mosaic/treemap, use grouped bar with same query.

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "tokens_saved")
  |> group(columns: ["optimization_type", "task_type"])
  |> sum()
  |> sort(columns: ["_value"], desc: true)
```

## 6. Histogram: Distribution of Tokens Saved per Event

```flux
import "experimental"

from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "tokens_saved")
  |> map(fn: (r) => ({ r with _value: float(v: r._value) }))
  |> experimental.histogram(bins: [0.0, 10.0, 25.0, 50.0, 100.0, 200.0, 400.0, 800.0, 1600.0], normalize: false)
```

## 7. Scatter: Original Tokens vs Optimized Tokens

Use `original_tokens` as X axis and `optimized_tokens` as Y axis.

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency_samples")
  |> filter(fn: (r) => r._field == "original_tokens" or r._field == "optimized_tokens" or r._field == "optimization_type")
  |> pivot(rowKey: ["_time", "task_type", "source", "optimization_type"], columnKey: ["_field"], valueColumn: "_value")
  |> limit(n: 500)
```

## 8. Simple Table: Top Optimization Types by Total Saved Tokens

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "tokens_saved")
  |> group(columns: ["optimization_type"])
  |> sum()
  |> sort(columns: ["_value"], desc: true)
```

## 9. Extra Meaningful Line: Rolling Prompt Savings Trend

This gives smoother trend lines instead of straight snapshots.

```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "prompt_efficiency" and r._field == "tokens_saved")
  |> aggregateWindow(every: 30m, fn: sum, createEmpty: false)
  |> movingAverage(n: 6)
```
