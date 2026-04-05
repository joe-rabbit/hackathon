# Hackathon Mochi

![Mochi Screenshot](image.png)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start local services (InfluxDB + Redpanda + Ollama):

```bash
docker compose up -d
```

Run the terminal app:

```bash
python -m tamagochi.app
```

Generate and push metrics:

```bash
python dashboard/agent_token_analyszer.py --log-dir logs --sources copilot,claude --skip-dedup
python dashboard/push_usage_to_influx.py --influx-url http://localhost:8086 --org hackathon --bucket metrics --token hackathon-dev-token --validate-measurements
```

Optional: run async Kafka stream pipeline:

```bash
python -u dashboard/kafka_stream_pipeline.py --token hackathon-dev-token --bootstrap-servers localhost:9092 --influx-url http://localhost:8086 --org hackathon --bucket metrics --mode all --from-start --validate-measurements --duration-s 10
```

## Structure

```text
hackthon-mochi/
├── dashboard/
│   ├── agent_token_analyszer.py
│   ├── push_usage_to_influx.py
│   ├── kafka_stream_pipeline.py
│   ├── simulate_dashboard_data.py
│   ├── influx_dashboard_import.json
│   ├── influx_dashboard_queries.md
│   ├── influx_dashboard_run_queries.md
│   ├── influx_script_builder.flux
│   ├── chat_dedup.py
│   └── green_prompt.py
├── tamagochi/
│   ├── app.py
│   ├── cat.html
│   ├── flower.html
│   └── connected_devices.json
├── pI/
│   └── copiolot_fastapi_status.py
├── logs/
│   ├── copilot_usage_log.jsonl
│   ├── prompt_efficiency_log.jsonl
│   └── influx_ingest_heartbeat.json
├── prompt_optimizer.py
├── gold_prompts.json
├── requirements.txt
├── docker-compose.yml
└── image.png
```

## Server Installation

- Codex
- PI

## Tamagochi Usage

Run:

```bash
python -m tamagochi.app
```

Hotkeys:

- `W`: walk
- `O`: optimize + sync metrics
- `P`: carbon plan (rank efficient devices)
- `F`: feed dispatch (CarbonMin allocation)
- `S`: scan carbon efficiency (loses life if not efficient)
- `N`: nap
- `q`: quit

Commands:

- `/help`
- `/connect <ip[,ip2...]>`
- `/devices`
- `/agents [ip[,ip2...]]`
- `/dashboard`
- `/level`
- `/flower`
- `/health`

# Server Installation
