#!/usr/bin/env python3
"""FastAPI status service for Copilot usage and energy metrics.

This service scans available Copilot logs, summarizes token usage with the
dashboard analyzer helpers, and exposes machine + usage metrics over HTTP so
the Tamagotchi app can fetch them from /status.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import psutil
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel


# Ensure project root is importable when running this file directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from dashboard import agent_token_analyszer as token_analyzer


KG_CO2E_PER_KWH = 0.4
ESTIMATED_TOKEN_THROUGHPUT_TPS = 45.0
BASE_ROUNDTRIP_LATENCY_MS = 120.0


class AgentMetric(BaseModel):
	name: str
	pid: int
	cpu: float
	memory_mb: float
	latency_ms: float
	importance: str
	energy_wh: float
	requests: int
	total_tokens: int


class StatusPayload(BaseModel):
	cpu_usage: float
	mem_usage: float
	temp: float
	energy_wh: float
	kg_co2e: float
	agents: list[AgentMetric]


def _build_analyzer_args(config: argparse.Namespace) -> argparse.Namespace:
	return argparse.Namespace(
		sessions_dir=config.sessions_dir,
		session_file=config.session_file,
		workspace_storage_root=config.workspace_storage_root,
		copilot_logs_dir=config.copilot_logs_dir,
	)


def _safe_cpu_temp() -> float:
	try:
		temps = psutil.sensors_temperatures()
	except Exception:
		return 0.0

	if not temps:
		return 0.0

	for entries in temps.values():
		for entry in entries:
			current = getattr(entry, "current", None)
			if current is not None:
				return float(current)
	return 0.0


def _importance_from_ratio(ratio: float) -> str:
	if ratio >= 0.5:
		return "high"
	if ratio >= 0.2:
		return "medium"
	return "low"


def _collect_metrics(config: argparse.Namespace) -> dict[str, Any]:
	analyzer_args = _build_analyzer_args(config)
	files = token_analyzer.discover_session_files(analyzer_args)

	summary: dict[str, token_analyzer.AgentStats] = {}
	if files:
		summary, _ = token_analyzer.summarize(files)

	totals = token_analyzer.aggregate_totals(summary)
	energy_wh, energy_kwh = token_analyzer.compute_energy(
		totals.total_tokens,
		config.wh_per_500_tokens,
	)

	# Use whole-system usage for device telemetry fields.
	cpu_usage = float(psutil.cpu_percent(interval=0.15))
	mem_usage = float(psutil.virtual_memory().percent)
	temp = _safe_cpu_temp()
	process_rss_mb = psutil.Process().memory_info().rss / (1024.0 * 1024.0)

	agents: list[AgentMetric] = []
	total_tokens = max(totals.total_tokens, 1)
	for agent_name, stats in sorted(
		summary.items(), key=lambda item: item[1].total_tokens, reverse=True
	):
		ratio = stats.total_tokens / total_tokens
		per_agent_energy_wh = energy_wh * ratio
		per_request_tokens = stats.total_tokens / max(stats.requests, 1)
		latency_ms = BASE_ROUNDTRIP_LATENCY_MS + (
			(per_request_tokens / ESTIMATED_TOKEN_THROUGHPUT_TPS) * 1000.0
		)

		agents.append(
			AgentMetric(
				name=agent_name,
				pid=0,
				# Token share is used as an estimate when process-level agent telemetry is unavailable.
				cpu=round(ratio * 100.0, 3),
				memory_mb=round(max(process_rss_mb * ratio, 1.0), 3),
				latency_ms=round(latency_ms, 3),
				importance=_importance_from_ratio(ratio),
				energy_wh=round(per_agent_energy_wh, 9),
				requests=stats.requests,
				total_tokens=stats.total_tokens,
			)
		)

	payload = StatusPayload(
		cpu_usage=round(cpu_usage, 3),
		mem_usage=round(mem_usage, 3),
		temp=round(temp, 3),
		energy_wh=round(energy_wh, 9),
		kg_co2e=round(energy_kwh * KG_CO2E_PER_KWH, 12),
		agents=agents,
	)
	return payload.model_dump()


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Serve Copilot usage and energy metrics over FastAPI",
	)
	parser.add_argument("--host", default=os.getenv("STATUS_HOST", "0.0.0.0"))
	parser.add_argument("--port", type=int, default=int(os.getenv("STATUS_PORT", "8000")))
	parser.add_argument("--wh-per-500-tokens", type=float, default=15.0)
	parser.add_argument("--sessions-dir", type=Path, default=None)
	parser.add_argument("--session-file", type=Path, action="append", default=[])
	parser.add_argument("--workspace-storage-root", type=Path, default=None)
	parser.add_argument(
		"--copilot-logs-dir",
		type=Path,
		default=PROJECT_ROOT / "logs" / "copilot_raw",
	)
	return parser.parse_args()


def create_app(config: argparse.Namespace) -> FastAPI:
	app = FastAPI(title="Copilot FastAPI Status", version="1.0.0")

	@app.get("/health")
	def health() -> dict[str, str]:
		return {"status": "ok"}

	@app.get("/status")
	def status() -> dict[str, Any]:
		return _collect_metrics(config)

	# Optional alias for convenience when exploring from browser/tools.
	@app.get("/agents")
	def agents() -> dict[str, Any]:
		metrics = _collect_metrics(config)
		return {
			"agents": metrics["agents"],
		}

	return app


def main() -> int:
	config = _parse_args()
	app = create_app(config)
	uvicorn.run(app, host=config.host, port=config.port)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
