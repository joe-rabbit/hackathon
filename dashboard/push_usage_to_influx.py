#!/usr/bin/env python3
"""Ingest Copilot usage snapshots from JSONL into InfluxDB.

This keeps InfluxDB as the single dashboard backend.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import time
from typing import Any
from urllib import parse, request

# Repo root = parent of dashboard/ (not parents[2], which is one level too high).
DEFAULT_LOG_PATH = (
    Path(__file__).resolve().parent.parent / "logs" / "copilot_usage_log.jsonl"
)
DEFAULT_PROMPT_EFFICIENCY_LOG_PATH = (
    Path(__file__).resolve().parent.parent / "logs" / "prompt_efficiency_log.jsonl"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Push usage snapshots from JSONL into InfluxDB line protocol."
    )
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument(
        "--prompt-efficiency-log-file",
        type=Path,
        default=DEFAULT_PROMPT_EFFICIENCY_LOG_PATH,
    )
    parser.add_argument("--influx-url", default="http://localhost:8086")
    parser.add_argument("--org", default="hackathon")
    parser.add_argument("--bucket", default="metrics")
    parser.add_argument("--token", required=True)
    parser.add_argument(
        "--grid-kg-co2e-per-kwh",
        type=float,
        default=0.4,
        help="Grid carbon intensity used to derive kg_co2e from kWh.",
    )
    parser.add_argument(
        "--since-lines",
        type=int,
        default=0,
        help="Only ingest the last N lines from JSONL (0 means all).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously tail JSONL and push only newly appended snapshots.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds for --watch mode (default: 2.0).",
    )
    parser.add_argument(
        "--watch-from-start",
        action="store_true",
        help="In watch mode, ingest existing lines first before tailing new lines.",
    )
    return parser.parse_args()


def escape_tag(value: str) -> str:
    return value.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def to_ns(timestamp_text: str) -> int:
    ts = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    return int(ts.timestamp() * 1_000_000_000)


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def build_lines(record: dict[str, Any], kg_per_kwh: float) -> list[str]:
    timestamp_raw = record.get("timestamp")
    if not isinstance(timestamp_raw, str):
        return []

    ts_ns = to_ns(timestamp_raw)
    totals = record.get("totals") if isinstance(record.get("totals"), dict) else {}
    energy = record.get("energy") if isinstance(record.get("energy"), dict) else {}
    models = record.get("models") if isinstance(record.get("models"), dict) else {}

    total_tokens = safe_int(totals.get("total_tokens"))
    requests_count = safe_int(totals.get("requests"))
    kwh = safe_float(energy.get("kwh"))
    wh_per_500_tokens = safe_float(energy.get("wh_per_500_tokens"))
    energy_source = str(energy.get("source", "manual"))
    mode = str(record.get("mode", "oneshot"))
    total_kg = kwh * kg_per_kwh

    lines: list[str] = []
    lines.append(
        "copilot_totals"
        f",energy_source={escape_tag(energy_source)},mode={escape_tag(mode)}"
        f" total_tokens={total_tokens}i,requests={requests_count}i,kwh={kwh},"
        f"wh_per_500_tokens={wh_per_500_tokens},kg_co2e={total_kg} {ts_ns}"
    )

    if total_tokens > 0 and models:
        for model_name, stats in models.items():
            if not isinstance(stats, dict):
                continue
            model_tokens = safe_int(stats.get("total_tokens"))
            if model_tokens <= 0:
                continue
            model_requests = safe_int(stats.get("requests"))
            share = model_tokens / total_tokens
            model_kwh = kwh * share
            model_kg = model_kwh * kg_per_kwh
            lines.append(
                "copilot_model_totals"
                f",model={escape_tag(str(model_name))},"
                f"energy_source={escape_tag(energy_source)},mode={escape_tag(mode)}"
                f" tokens={model_tokens}i,requests={model_requests}i,"
                f"kwh_estimate={model_kwh},kg_co2e={model_kg} {ts_ns}"
            )

    sources = record.get("sources")
    if isinstance(sources, dict) and total_tokens > 0:
        for src_name, block in sources.items():
            if not isinstance(block, dict) or not isinstance(src_name, str):
                continue
            tdata = block.get("totals")
            if not isinstance(tdata, dict):
                continue
            st_tokens = safe_int(tdata.get("total_tokens"))
            st_req = safe_int(tdata.get("requests"))
            if st_tokens <= 0:
                continue
            share = st_tokens / total_tokens
            st_kwh = kwh * share
            st_kg = st_kwh * kg_per_kwh
            lines.append(
                "ai_usage_totals"
                f",source={escape_tag(src_name)},"
                f"energy_source={escape_tag(energy_source)},mode={escape_tag(mode)}"
                f" total_tokens={st_tokens}i,requests={st_req}i,kwh={st_kwh},"
                f"kg_co2e={st_kg} {ts_ns}"
            )

    po = record.get("prompt_optimization")
    if isinstance(po, dict):
        tier = str(po.get("tier", "laptop"))
        opt_type = str(po.get("optimization_type", "prompt"))
        tokens_o = safe_int(po.get("tokens_original_est"))
        tokens_c = safe_int(po.get("tokens_compressed_est"))
        tokens_saved = safe_int(po.get("tokens_saved"))
        carbon_saved = safe_float(po.get("carbon_saved_g"))
        eff = safe_float(po.get("efficiency_ratio"))
        lines.append(
            "prompt_optimization"
            f",optimization_type={escape_tag(opt_type)},tier={escape_tag(tier)}"
            f" tokens_original_est={tokens_o}i,tokens_compressed_est={tokens_c}i,"
            f"tokens_saved={tokens_saved}i,carbon_saved_g={carbon_saved},"
            f"efficiency_ratio={eff} {ts_ns}"
        )

    dedup = record.get("dedup")
    if isinstance(dedup, dict):
        status = str(dedup.get("status", "unknown"))
        threshold = safe_float(dedup.get("threshold"))
        pairs_found = safe_int(dedup.get("pairs_found"))
        tokens_saved_total = safe_int(dedup.get("tokens_saved_if_cached_total"))
        source_files_count = safe_int(dedup.get("source_files_count"))
        max_similarity = safe_float(dedup.get("max_similarity_score"))
        lines.append(
            "prompt_dedup"
            f",status={escape_tag(status)}"
            f" pairs_found={pairs_found}i,"
            f"tokens_saved_if_cached_total={tokens_saved_total}i,"
            f"source_files_count={source_files_count}i,"
            f"threshold={threshold},max_similarity_score={max_similarity} {ts_ns}"
        )

    return lines


def build_prompt_efficiency_lines(record: dict[str, Any]) -> list[str]:
    timestamp_raw = record.get("timestamp")
    if not isinstance(timestamp_raw, str):
        return []
    ts_ns = to_ns(timestamp_raw)
    optimization_type = str(record.get("optimization_type", "unknown"))
    task_type = str(record.get("task_type", "general"))
    source = str(record.get("source", "unknown"))
    original_tokens = safe_int(record.get("original_tokens"))
    optimized_tokens = safe_int(record.get("optimized_tokens"))
    tokens_saved = safe_int(record.get("tokens_saved"))
    carbon_saved_g = safe_float(record.get("carbon_saved_g"))
    max_tokens_before = safe_int(record.get("max_tokens_before"))
    max_tokens_after = safe_int(record.get("max_tokens_after"))
    return [
        "prompt_efficiency"
        f",optimization_type={escape_tag(optimization_type)},"
        f"task_type={escape_tag(task_type)},source={escape_tag(source)}"
        f" original_tokens={original_tokens}i,optimized_tokens={optimized_tokens}i,"
        f"tokens_saved={tokens_saved}i,carbon_saved_g={carbon_saved_g},"
        f"max_tokens_before={max_tokens_before}i,max_tokens_after={max_tokens_after}i {ts_ns}"
    ]


def read_jsonl(path: Path, since_lines: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        lines = [line.strip() for line in f if line.strip()]

    if since_lines > 0:
        lines = lines[-since_lines:]

    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def parse_record(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    if isinstance(value, dict):
        return value
    return None


def read_new_records(path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], offset

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        end = f.tell()
        # Handle file truncation/rotation by restarting at the beginning.
        if offset > end:
            offset = 0
        f.seek(offset)
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            record = parse_record(line)
            if record is not None:
                records.append(record)
        return records, f.tell()


def write_to_influx(url: str, org: str, bucket: str, token: str, body: str) -> None:
    endpoint = (
        f"{url.rstrip('/')}"
        + "/api/v2/write?"
        + parse.urlencode({"org": org, "bucket": bucket, "precision": "ns"})
    )
    req = request.Request(
        endpoint,
        data=body.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "text/plain; charset=utf-8",
            "Accept": "application/json",
        },
    )
    with request.urlopen(req, timeout=30) as resp:
        if resp.status not in (204, 200):
            raise RuntimeError(f"Influx write failed: HTTP {resp.status}")


def ingest_records(
    records: list[dict[str, Any]],
    influx_url: str,
    org: str,
    bucket: str,
    token: str,
    kg_per_kwh: float,
) -> tuple[int, int]:
    if not records:
        return 0, 0

    lines: list[str] = []
    for record in records:
        lines.extend(build_lines(record, kg_per_kwh))

    if not lines:
        return len(records), 0

    write_to_influx(influx_url, org, bucket, token, "\n".join(lines))
    return len(records), len(lines)


def ingest_prompt_efficiency_records(
    records: list[dict[str, Any]],
    influx_url: str,
    org: str,
    bucket: str,
    token: str,
) -> tuple[int, int]:
    if not records:
        return 0, 0

    lines: list[str] = []
    for record in records:
        lines.extend(build_prompt_efficiency_lines(record))

    if not lines:
        return len(records), 0

    write_to_influx(influx_url, org, bucket, token, "\n".join(lines))
    return len(records), len(lines)


def run_watch(args: argparse.Namespace) -> int:
    interval = max(args.interval, 0.2)
    offset = 0
    prompt_offset = 0

    if args.watch_from_start:
        existing = read_jsonl(args.log_file, since_lines=0)
        ingested_records, ingested_points = ingest_records(
            existing,
            args.influx_url,
            args.org,
            args.bucket,
            args.token,
            args.grid_kg_co2e_per_kwh,
        )
        prompt_existing = read_jsonl(args.prompt_efficiency_log_file, since_lines=0)
        _, prompt_points = ingest_prompt_efficiency_records(
            prompt_existing,
            args.influx_url,
            args.org,
            args.bucket,
            args.token,
        )
        print(
            f"Initial ingest complete: {ingested_records} snapshots, {ingested_points + prompt_points} points."
        )
    elif args.log_file.exists():
        with args.log_file.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            offset = f.tell()
    if args.prompt_efficiency_log_file.exists():
        with args.prompt_efficiency_log_file.open(
            "r", encoding="utf-8", errors="replace"
        ) as f:
            f.seek(0, 2)
            prompt_offset = f.tell()

    print(
        f"Watching {args.log_file} and {args.prompt_efficiency_log_file} every {interval:.1f}s. Press Ctrl+C to stop."
    )

    try:
        while True:
            records, offset = read_new_records(args.log_file, offset)
            prompt_records, prompt_offset = read_new_records(
                args.prompt_efficiency_log_file, prompt_offset
            )
            ingested_records, ingested_points = ingest_records(
                records,
                args.influx_url,
                args.org,
                args.bucket,
                args.token,
                args.grid_kg_co2e_per_kwh,
            )
            prompt_ingested_records, prompt_ingested_points = (
                ingest_prompt_efficiency_records(
                    prompt_records,
                    args.influx_url,
                    args.org,
                    args.bucket,
                    args.token,
                )
            )
            if ingested_points > 0 or prompt_ingested_points > 0:
                print(
                    f"[{time.strftime('%H:%M:%S')}] Ingested {ingested_records} snapshots and "
                    f"{prompt_ingested_records} prompt-efficiency records as "
                    f"{ingested_points + prompt_ingested_points} points."
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped watch mode.")
        return 0


def resolve_log_path(args: argparse.Namespace) -> Path:
    """Prefer repo logs/; if missing, try ./logs from cwd (run analyzer from repo root)."""
    primary = args.log_file.resolve()
    if primary.exists():
        return primary
    using_default = args.log_file.resolve() == DEFAULT_LOG_PATH.resolve()
    if using_default:
        fallback = (Path.cwd() / "logs" / "copilot_usage_log.jsonl").resolve()
        if fallback.exists():
            return fallback
    return primary


def resolve_prompt_efficiency_log_path(args: argparse.Namespace) -> Path:
    primary = args.prompt_efficiency_log_file.resolve()
    if primary.exists():
        return primary
    using_default = (
        args.prompt_efficiency_log_file.resolve()
        == DEFAULT_PROMPT_EFFICIENCY_LOG_PATH.resolve()
    )
    if using_default:
        fallback = (Path.cwd() / "logs" / "prompt_efficiency_log.jsonl").resolve()
        if fallback.exists():
            return fallback
    return primary


def main() -> int:
    args = parse_args()
    args.prompt_efficiency_log_file = resolve_prompt_efficiency_log_path(args)
    if args.watch:
        args.log_file = resolve_log_path(args)
        return run_watch(args)

    log_path = resolve_log_path(args)
    prompt_efficiency_log_path = resolve_prompt_efficiency_log_path(args)
    records = read_jsonl(log_path, args.since_lines)
    prompt_efficiency_records = read_jsonl(
        prompt_efficiency_log_path, args.since_lines
    )
    if not records and not prompt_efficiency_records:
        print("No snapshot records found to ingest.")
        print(f"  Expected file: {log_path}")
        print(f"  Exists: {log_path.exists()}")
        if log_path.exists():
            text = log_path.read_text(encoding="utf-8", errors="replace")
            nonempty = sum(1 for line in text.splitlines() if line.strip())
            print(f"  Non-empty lines: {nonempty} (JSON parse may have failed)")
        else:
            print("  Run: python dashboard/agent_token_analyszer.py --log-dir logs")
            print("  Or:  python dashboard/push_usage_to_influx.py --log-file logs/copilot_usage_log.jsonl")
        return 1

    ingested_records, ingested_points = ingest_records(
        records,
        args.influx_url,
        args.org,
        args.bucket,
        args.token,
        args.grid_kg_co2e_per_kwh,
    )
    prompt_ingested_records, prompt_ingested_points = (
        ingest_prompt_efficiency_records(
            prompt_efficiency_records,
            args.influx_url,
            args.org,
            args.bucket,
            args.token,
        )
    )
    if ingested_points == 0 and prompt_ingested_points == 0:
        print("No valid points generated from snapshots.")
        return 1

    print(
        f"Ingested {ingested_records} snapshots and {prompt_ingested_records} prompt-efficiency "
        f"records as {ingested_points + prompt_ingested_points} points into InfluxDB."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
