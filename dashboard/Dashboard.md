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
