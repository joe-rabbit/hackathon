# Mochi Dashboard UI Specification

This document describes the Streamlit dashboard for the Edge AI Orchestrator.

## Pages

1. **Home (app.py)** - Main overview with summary metrics
2. **Overview** - System-wide charts and status distribution
3. **Agents** - Individual agent details with gauges
4. **Optimizer Impact** - Before/after comparison charts
5. **Events** - Alert and timeline views

## Features

- Real-time metrics refresh
- Interactive Plotly charts
- Agent selector for drill-down
- Severity-filtered alert views
- Event timeline with filtering

## Run Command

```bash
streamlit run dashboard/app.py
```

Dashboard URL: http://127.0.0.1:8501
# Carbon Footprint Dashboard (InfluxDB Only)

This project uses InfluxDB as the single backend and dashboard UI.

## Data Flow

1. Snapshot producer writes JSONL records:
   - hackathon/dashboard/agent_token_analyszer.py
   - logs/copilot_usage_log.jsonl
2. Influx writer reads JSONL and writes points:
   - hackathon/dashboard/push_usage_to_influx.py
   - bucket: metrics
3. Influx dashboard reads from measurements:
   - copilot_totals
   - copilot_model_totals

## Quick Start

Run one-time import:

```powershell
c:/Users/josep/hackathon/.venv/Scripts/python.exe hackathon/dashboard/push_usage_to_influx.py `
	--influx-url http://localhost:8086 `
	--org hackathon `
	--bucket metrics `
	--token hackathon-dev-token `
	--grid-kg-co2e-per-kwh 0.4
```

## Live Mode (Recommended)

Use two terminals to keep the dashboard updating continuously.

Terminal A: generate snapshots continuously

```powershell
c:/Users/josep/hackathon/.venv/Scripts/python.exe hackathon/dashboard/agent_token_analyszer.py --watch
```

Terminal B: ingest new snapshots continuously

```powershell
c:/Users/josep/hackathon/.venv/Scripts/python.exe hackathon/dashboard/push_usage_to_influx.py `
	--influx-url http://localhost:8086 `
	--org hackathon `
	--bucket metrics `
	--token hackathon-dev-token `
	--grid-kg-co2e-per-kwh 0.4 `
	--watch
```

First-time replay + watch:

```powershell
c:/Users/josep/hackathon/.venv/Scripts/python.exe hackathon/dashboard/push_usage_to_influx.py `
	--influx-url http://localhost:8086 `
	--org hackathon `
	--bucket metrics `
	--token hackathon-dev-token `
	--grid-kg-co2e-per-kwh 0.4 `
	--watch --watch-from-start
```

## Dashboard Setup in Influx UI

1. Open http://localhost:8086
2. Create a dashboard named Carbon Footprint
3. Add cells using queries from hackathon/dashboard/influx_dashboard_queries.md
4. Set dashboard auto-refresh to 5s or 10s

## Recommended Cells and Visualizations

1. Latest Total Energy (kWh): Single Stat
2. Latest Total CO2e (kg): Single Stat
3. Energy Over Time: Graph
4. CO2e Over Time: Graph
5. Incremental Energy per Snapshot: Graph
6. Top Models by CO2e: Simple Table or Table
7. Top Models by Energy: Simple Table or Table

## Measurements and Fields

copilot_totals:

- tags: energy_source, mode
- fields: total_tokens, requests, kwh, wh_per_500_tokens, kg_co2e

copilot_model_totals:

- tags: model, energy_source, mode
- fields: tokens, requests, kwh_estimate, kg_co2e

## Troubleshooting

If graphs look stale:

1. Confirm both watch commands are running
2. Confirm Influx dashboard auto-refresh is enabled
3. Confirm new lines are being appended to logs/copilot_usage_log.jsonl

If no data appears:

1. Check Influx URL, org, bucket, and token in writer command
2. Run one-time import command and verify it reports ingested points
3. In Influx Data Explorer, query measurement copilot_totals for last 30d
