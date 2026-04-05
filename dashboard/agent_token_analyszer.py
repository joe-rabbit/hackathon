#!/usr/bin/env python3
"""Calculate token usage per Copilot agent from VS Code chat session JSONL files.

This script prefers real usage counters from session payloads when available.
If a request has no token counters, it falls back to a simple text-length estimate.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TOKEN_KEY_SETS = (
    ("promptTokens", "completionTokens", "totalTokens"),
    ("prompt_tokens", "completion_tokens", "total_tokens"),
    ("inputTokens", "outputTokens", "totalTokens"),
    ("input_tokens", "output_tokens", "total_tokens"),
)


@dataclass
class AgentStats:
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    actual_requests: int = 0
    estimated_requests: int = 0


@dataclass(frozen=True)
class HardwareProfile:
    fp8_peak_pflops: float
    rack_power_kw: float


HARDWARE_PROFILES: dict[str, HardwareProfile] = {
    "h100-8x": HardwareProfile(fp8_peak_pflops=31.66, rack_power_kw=10.2),
    "gb200-nvl72": HardwareProfile(fp8_peak_pflops=180.0, rack_power_kw=120.0),
}


# Purpose: Define CLI options for session discovery, reporting, and energy/hardware modeling.
# Inputs: None.
# Outputs: Parsed argparse.Namespace.
# Side Effects: Reads command-line arguments from process invocation.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Copilot token usage per agent from VS Code chatSessions and Copilot logs."
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Path to a VS Code chatSessions directory. If omitted, auto-discovery is used.",
    )
    parser.add_argument(
        "--session-file",
        type=Path,
        action="append",
        default=[],
        help="Specific .jsonl session file(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--workspace-storage-root",
        type=Path,
        default=None,
        help="Path to workspaceStorage root (contains many IDs and chatSessions).",
    )
    parser.add_argument(
        "--copilot-logs-dir",
        type=Path,
        default=Path("logs") / "copilot_raw",
        help="Directory with copied Copilot chat/session logs (default: ./logs/copilot_raw).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously stream updates as session logs change.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Refresh interval in seconds for --watch mode (default: 1.0).",
    )
    parser.add_argument(
        "--wh-per-500-tokens",
        type=float,
        default=15.0,
        help="Energy factor in watt-hours per 500 tokens (default: 15).",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory where usage snapshots are stored (default: ./logs).",
    )
    parser.add_argument(
        "--hardware-profile",
        choices=["none", "h100-8x", "gb200-nvl72"],
        default="none",
        help="Optional hardware model for compute and energy estimates.",
    )
    parser.add_argument(
        "--profile-fp8-pflops",
        type=float,
        default=None,
        help="Override hardware profile FP8 peak throughput in PFLOPS.",
    )
    parser.add_argument(
        "--rack-power-kw",
        type=float,
        default=None,
        help="Override hardware rack/node power draw in kW.",
    )
    parser.add_argument(
        "--mfu",
        type=float,
        default=0.60,
        help="Model FLOPs utilization for hardware estimate (default: 0.60).",
    )
    parser.add_argument(
        "--model-params-billions",
        type=float,
        default=175.0,
        help="Model parameter count in billions for FLOPs estimate (default: 175).",
    )
    parser.add_argument(
        "--request-tokens",
        type=int,
        default=500,
        help="Token count per representative request for compute estimate (default: 500).",
    )
    parser.add_argument(
        "--e2e-latency-s",
        type=float,
        default=5.3,
        help="End-to-end latency in seconds for wall-clock energy estimate (default: 5.3).",
    )
    parser.add_argument(
        "--profile-energy-mode",
        choices=["compute", "e2e"],
        default="e2e",
        help="Profile energy source when using hardware profile for totals.",
    )
    parser.add_argument(
        "--use-profile-energy",
        action="store_true",
        help="Use hardware profile energy (compute/e2e) instead of --wh-per-500-tokens for totals.",
    )
    return parser.parse_args()


# Purpose: Aggregate per-key usage stats into one combined totals record.
# Inputs: summary - Mapping of entity name to AgentStats.
# Outputs: AgentStats totals instance.
# Side Effects: None.
def aggregate_totals(summary: dict[str, AgentStats]) -> AgentStats:
    totals = AgentStats()
    for stats in summary.values():
        totals.requests += stats.requests
        totals.prompt_tokens += stats.prompt_tokens
        totals.completion_tokens += stats.completion_tokens
        totals.total_tokens += stats.total_tokens
        totals.actual_requests += stats.actual_requests
        totals.estimated_requests += stats.estimated_requests
    return totals


# Purpose: Convert token totals to energy estimates based on Wh-per-500-token factor.
# Inputs: total_tokens - token count; wh_per_500_tokens - model factor.
# Outputs: Tuple of (watt_hours, kilo_watt_hours).
# Side Effects: None.
def compute_energy(total_tokens: int, wh_per_500_tokens: float) -> tuple[float, float]:
    watt_hours = (total_tokens / 500.0) * wh_per_500_tokens
    kilo_watt_hours = watt_hours / 1000.0
    return watt_hours, kilo_watt_hours


# Purpose: Resolve hardware profile parameters and derive FLOPs/time/energy coefficients.
# Inputs: args - Parsed CLI options.
# Outputs: Hardware metrics dictionary or None when profile is disabled.
# Side Effects: None.
def resolve_hardware_profile(args: argparse.Namespace) -> dict[str, float] | None:
    if args.hardware_profile == "none":
        return None

    profile = HARDWARE_PROFILES[args.hardware_profile]
    fp8_peak_pflops = (
        args.profile_fp8_pflops
        if args.profile_fp8_pflops is not None
        else profile.fp8_peak_pflops
    )
    rack_power_kw = (
        args.rack_power_kw if args.rack_power_kw is not None else profile.rack_power_kw
    )
    mfu = max(args.mfu, 0.01)
    request_tokens = max(args.request_tokens, 1)
    model_params_billions = max(args.model_params_billions, 0.001)
    e2e_latency_s = max(args.e2e_latency_s, 0.001)

    total_flops = 2.0 * (model_params_billions * 1_000_000_000.0) * request_tokens
    effective_flops = fp8_peak_pflops * 1_000_000_000_000_000.0 * mfu
    compute_time_s = total_flops / effective_flops

    rack_power_w = rack_power_kw * 1000.0
    compute_wh_per_request = (rack_power_w * compute_time_s) / 3600.0
    e2e_wh_per_request = (rack_power_w * e2e_latency_s) / 3600.0

    scale_to_500 = 500.0 / request_tokens
    wh_per_500_compute = compute_wh_per_request * scale_to_500
    wh_per_500_e2e = e2e_wh_per_request * scale_to_500

    return {
        "fp8_peak_pflops": fp8_peak_pflops,
        "rack_power_kw": rack_power_kw,
        "mfu": mfu,
        "model_params_billions": model_params_billions,
        "request_tokens": float(request_tokens),
        "e2e_latency_s": e2e_latency_s,
        "total_flops": total_flops,
        "effective_flops": effective_flops,
        "compute_time_s": compute_time_s,
        "compute_wh_per_request": compute_wh_per_request,
        "e2e_wh_per_request": e2e_wh_per_request,
        "wh_per_500_compute": wh_per_500_compute,
        "wh_per_500_e2e": wh_per_500_e2e,
    }


# Purpose: Select active Wh-per-500-token factor source (manual or hardware-derived).
# Inputs: args - Parsed CLI options; hardware - Optional derived hardware metrics.
# Outputs: Tuple of (wh_per_500_tokens, source_label).
# Side Effects: None.
def choose_wh_per_500_tokens(
    args: argparse.Namespace,
    hardware: dict[str, float] | None,
) -> tuple[float, str]:
    if args.use_profile_energy and hardware is not None:
        if args.profile_energy_mode == "compute":
            return hardware["wh_per_500_compute"], "hardware-compute"
        return hardware["wh_per_500_e2e"], "hardware-e2e"
    return args.wh_per_500_tokens, "manual"


# Purpose: Persist one usage snapshot record to JSONL for later analysis.
# Inputs: log_dir, summary, model_summary, files_scanned, energy settings, mode.
# Outputs: Path to appended JSONL file.
# Side Effects: Creates log directory and appends one line to disk.
def write_usage_snapshot(
    log_dir: Path,
    summary: dict[str, AgentStats],
    model_summary: dict[str, AgentStats],
    files_scanned: int,
    wh_per_500_tokens: float,
    energy_source: str,
    hardware: dict[str, float] | None,
    mode: str,
) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    out_file = log_dir / "copilot_usage_log.jsonl"
    totals = aggregate_totals(summary)
    energy_wh, energy_kwh = compute_energy(totals.total_tokens, wh_per_500_tokens)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "files_scanned": files_scanned,
        "energy": {
            "source": energy_source,
            "wh_per_500_tokens": wh_per_500_tokens,
            "watt_hours": round(energy_wh, 6),
            "kwh": round(energy_kwh, 6),
        },
        "totals": {
            "requests": totals.requests,
            "prompt_tokens": totals.prompt_tokens,
            "completion_tokens": totals.completion_tokens,
            "total_tokens": totals.total_tokens,
            "actual_requests": totals.actual_requests,
            "estimated_requests": totals.estimated_requests,
        },
        "agents": {
            agent: {
                "requests": stats.requests,
                "prompt_tokens": stats.prompt_tokens,
                "completion_tokens": stats.completion_tokens,
                "total_tokens": stats.total_tokens,
                "actual_requests": stats.actual_requests,
                "estimated_requests": stats.estimated_requests,
            }
            for agent, stats in summary.items()
        },
        "models": {
            model: {
                "requests": stats.requests,
                "prompt_tokens": stats.prompt_tokens,
                "completion_tokens": stats.completion_tokens,
                "total_tokens": stats.total_tokens,
                "actual_requests": stats.actual_requests,
                "estimated_requests": stats.estimated_requests,
            }
            for model, stats in model_summary.items()
        },
    }
    if hardware is not None:
        record["hardware"] = hardware

    with out_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")

    return out_file


# Purpose: Print resolved hardware timing and energy factors to console.
# Inputs: hardware_profile - Profile name; hardware - Derived metrics dictionary.
# Outputs: None.
# Side Effects: Writes text to stdout.
def print_hardware_estimate(hardware_profile: str, hardware: dict[str, float]) -> None:
    print()
    print(f"Hardware profile: {hardware_profile}")
    print(
        f"Compute estimate ({int(hardware['request_tokens'])} tokens): "
        f"{hardware['compute_time_s'] * 1000.0:.3f} ms"
    )
    print(
        f"Energy per request: compute={hardware['compute_wh_per_request']:.6f} Wh, "
        f"e2e={hardware['e2e_wh_per_request']:.6f} Wh"
    )
    print(
        f"Derived factor per 500 tokens: compute={hardware['wh_per_500_compute']:.6f} Wh, "
        f"e2e={hardware['wh_per_500_e2e']:.6f} Wh"
    )


# Purpose: Locate default VS Code workspaceStorage directories across OSes.
# Inputs: None.
# Outputs: Existing workspaceStorage roots.
# Side Effects: None.
def default_workspace_storage_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        # Linux
        home / ".config" / "Code" / "User" / "workspaceStorage",
        home / ".config" / "Code - OSS" / "User" / "workspaceStorage",
        # macOS
        home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage",
        home / "Library" / "Application Support" / "Code - OSS" / "User" / "workspaceStorage",
        # Windows
        home / "AppData" / "Roaming" / "Code" / "User" / "workspaceStorage",
        home / "AppData" / "Roaming" / "Code - OSS" / "User" / "workspaceStorage",
    ]
    return [p for p in candidates if p.exists()]


# Purpose: Locate default VS Code log directories across OSes.
# Inputs: None.
# Outputs: Existing VS Code log roots.
# Side Effects: None.
def default_vscode_log_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        # Linux
        home / ".config" / "Code" / "logs",
        home / ".config" / "Code - OSS" / "logs",
        # macOS
        home / "Library" / "Application Support" / "Code" / "logs",
        home / "Library" / "Application Support" / "Code - OSS" / "logs",
        # Windows
        home / "AppData" / "Roaming" / "Code" / "logs",
        home / "AppData" / "Roaming" / "Code - OSS" / "logs",
    ]
    return [p for p in candidates if p.exists()]


# Purpose: Discover session JSONL files from explicit, directory, or auto-discovered sources.
# Inputs: args - Parsed CLI options.
# Outputs: Sorted list of existing JSONL paths.
# Side Effects: Reads filesystem metadata.
def discover_session_files(args: argparse.Namespace) -> list[Path]:
    if args.session_file:
        return [p for p in args.session_file if p.exists()]

    files: set[Path] = set()

    # First priority: explicit sessions directory.
    if args.sessions_dir:
        files.update(p for p in args.sessions_dir.rglob("*.jsonl") if p.is_file())
        files.update(p for p in args.sessions_dir.rglob("*.log") if p.is_file())

    # Second priority: copied local logs folder in this project.
    copilot_logs_dir = getattr(args, "copilot_logs_dir", None)
    if copilot_logs_dir and isinstance(copilot_logs_dir, Path) and copilot_logs_dir.exists():
        files.update(p for p in copilot_logs_dir.rglob("*.jsonl") if p.is_file())
        files.update(p for p in copilot_logs_dir.rglob("*.log") if p.is_file())

    # If we already found logs from explicit/local sources, return those.
    if files:
        return sorted(files)

    roots: list[Path] = []
    if args.workspace_storage_root and args.workspace_storage_root.exists():
        roots.append(args.workspace_storage_root)
    else:
        roots.extend(default_workspace_storage_roots())

    for root in roots:
        if not root.exists():
            continue
        for ws in root.iterdir():
            if not ws.is_dir():
                continue
            sessions_dir = ws / "chatSessions"
            if sessions_dir.exists() and sessions_dir.is_dir():
                files.update(p for p in sessions_dir.glob("*.jsonl") if p.is_file())

            # Copilot Chat extension storage files can also contain JSONL events.
            copilot_chat_dir = ws / "GitHub.copilot-chat"
            if copilot_chat_dir.exists() and copilot_chat_dir.is_dir():
                files.update(p for p in copilot_chat_dir.rglob("*.jsonl") if p.is_file())
                files.update(p for p in copilot_chat_dir.rglob("*.log") if p.is_file())

    # Also include VS Code runtime log directories with Copilot/Chat event logs.
    for log_root in default_vscode_log_roots():
        for p in log_root.rglob("*.jsonl"):
            if p.is_file() and ("copilot" in str(p).lower() or "chat" in str(p).lower()):
                files.add(p)
        for p in log_root.rglob("*.log"):
            if p.is_file() and ("copilot" in str(p).lower() or "chat" in str(p).lower()):
                files.add(p)

    return sorted(files)


# Purpose: Normalize scalar values to int for token fields when valid.
# Inputs: value - Any token-like field value.
# Outputs: int value or None when unsupported.
# Side Effects: None.
def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


# Purpose: Map multiple usage key schemas to one (prompt, completion, total) tuple.
# Inputs: d - Dictionary potentially containing usage counters.
# Outputs: Token tuple or None when not present.
# Side Effects: None.
def normalize_usage(d: dict[str, Any]) -> tuple[int, int, int] | None:
    for prompt_key, completion_key, total_key in TOKEN_KEY_SETS:
        prompt = as_int(d.get(prompt_key))
        completion = as_int(d.get(completion_key))
        total = as_int(d.get(total_key))

        if prompt is None and completion is None and total is None:
            continue

        prompt = prompt or 0
        completion = completion or 0
        total = total if total is not None else prompt + completion
        return prompt, completion, total

    return None


# Purpose: Recursively scan nested objects and yield all normalized usage tuples.
# Inputs: obj - Any nested dict/list structure.
# Outputs: Iterable of usage tuples.
# Side Effects: None.
def find_usage_objects(obj: Any) -> Iterable[tuple[int, int, int]]:
    if isinstance(obj, dict):
        usage = normalize_usage(obj)
        if usage is not None:
            yield usage
        for value in obj.values():
            yield from find_usage_objects(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from find_usage_objects(item)


# Purpose: Estimate token count from text length as fallback when counters are missing.
# Inputs: text - Source text.
# Outputs: Estimated token integer.
# Side Effects: None.
def estimate_tokens_from_text(text: str) -> int:
    # Rough approximation that is stable across mixed code/plain text.
    if not text.strip():
        return 0
    return int(math.ceil(len(text) / 4.0))


# Purpose: Collect textual response content used by fallback token estimation.
# Inputs: response_items - Response payload list.
# Outputs: Concatenated text payload.
# Side Effects: None.
def collect_response_text(response_items: Any) -> str:
    if not isinstance(response_items, list):
        return ""

    chunks: list[str] = []
    for item in response_items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        value = item.get("value")
        if isinstance(value, str) and (
            kind is None or kind in {"text", "markdownContent"}
        ):
            chunks.append(value)
    return "\n".join(chunks)


# Purpose: Extract request dictionaries from one parsed session-log line.
# Inputs: line_obj - Parsed JSON object from a JSONL row.
# Outputs: List of request dictionaries.
# Side Effects: None.
def extract_requests_from_line(line_obj: dict[str, Any]) -> list[dict[str, Any]]:
    kind = line_obj.get("kind")
    if kind == 2 and line_obj.get("k") == ["requests"]:
        value = line_obj.get("v")
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []


# Purpose: Determine model identifier string for a request record.
# Inputs: req - Request dictionary.
# Outputs: Model identifier string, or "unknown".
# Side Effects: None.
def extract_model_name(req: dict[str, Any]) -> str:
    model_id = req.get("modelId")
    if isinstance(model_id, str) and model_id.strip():
        return model_id.strip()

    input_state = req.get("inputState")
    if isinstance(input_state, dict):
        selected_model = input_state.get("selectedModel")
        if isinstance(selected_model, dict):
            identifier = selected_model.get("identifier")
            if isinstance(identifier, str) and identifier.strip():
                return identifier.strip()
            metadata = selected_model.get("metadata")
            if isinstance(metadata, dict):
                version = metadata.get("version")
                if isinstance(version, str) and version.strip():
                    return version.strip()

    return "unknown"


# Purpose: Accumulate one request into per-agent and per-model counters.
# Inputs: req plus mutable summary dictionaries.
# Outputs: None.
# Side Effects: Mutates summary and model_summary dictionaries.
def process_request(
    req: dict[str, Any],
    summary: dict[str, AgentStats],
    model_summary: dict[str, AgentStats],
) -> None:
    agent_info = req.get("agent") if isinstance(req.get("agent"), dict) else {}
    agent_name = (
        agent_info.get("name")
        or agent_info.get("fullName")
        or agent_info.get("id")
        or "unknown"
    )

    model_name = extract_model_name(req)

    stats = summary.setdefault(agent_name, AgentStats())
    model_stats = model_summary.setdefault(model_name, AgentStats())
    stats.requests += 1
    model_stats.requests += 1

    usage_entries = list(find_usage_objects(req))
    if usage_entries:
        stats.actual_requests += 1
        model_stats.actual_requests += 1
        for prompt, completion, total in usage_entries:
            stats.prompt_tokens += prompt
            stats.completion_tokens += completion
            stats.total_tokens += total
            model_stats.prompt_tokens += prompt
            model_stats.completion_tokens += completion
            model_stats.total_tokens += total
    else:
        stats.estimated_requests += 1
        model_stats.estimated_requests += 1
        request_text = ""
        message = req.get("message")
        if isinstance(message, dict) and isinstance(message.get("text"), str):
            request_text = message["text"]
        response_text = collect_response_text(req.get("response"))
        prompt = estimate_tokens_from_text(request_text)
        completion = estimate_tokens_from_text(response_text)
        total = prompt + completion
        stats.prompt_tokens += prompt
        stats.completion_tokens += completion
        stats.total_tokens += total
        model_stats.prompt_tokens += prompt
        model_stats.completion_tokens += completion
        model_stats.total_tokens += total


# Purpose: Parse one raw JSONL line and accumulate contained request records.
# Inputs: raw line text plus mutable summary dictionaries.
# Outputs: Count of processed requests from this line.
# Side Effects: Mutates summary and model_summary dictionaries.
def process_jsonl_line(
    raw: str,
    summary: dict[str, AgentStats],
    model_summary: dict[str, AgentStats],
) -> int:
    raw = raw.strip()
    if not raw:
        return 0

    try:
        line_obj = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    processed = 0
    for req in extract_requests_from_line(line_obj):
        process_request(req, summary, model_summary)
        processed += 1
    return processed


# Purpose: Build complete per-agent and per-model summaries from all files.
# Inputs: files - List of session JSONL paths.
# Outputs: Tuple of (summary, model_summary).
# Side Effects: Reads session files from disk.
def summarize(files: list[Path]) -> tuple[dict[str, AgentStats], dict[str, AgentStats]]:
    summary: dict[str, AgentStats] = {}
    model_summary: dict[str, AgentStats] = {}

    for file_path in files:
        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                process_jsonl_line(raw, summary, model_summary)

    return summary, model_summary


# Purpose: Tail session logs continuously and emit incremental reports/snapshots.
# Inputs: args - Parsed CLI options.
# Outputs: Process exit code.
# Side Effects: Reads logs repeatedly, prints to stdout, appends snapshot file.
def stream_summary(args: argparse.Namespace) -> int:
    summary: dict[str, AgentStats] = {}
    model_summary: dict[str, AgentStats] = {}
    offsets: dict[Path, int] = {}
    interval = max(args.interval, 0.1)
    files_scanned = 0
    hardware = resolve_hardware_profile(args)
    wh_per_500_tokens, energy_source = choose_wh_per_500_tokens(args, hardware)

    print(
        f"Watching Copilot session logs (refresh every {interval:.1f}s). Press Ctrl+C to stop."
    )
    print()

    try:
        while True:
            files = discover_session_files(args)
            files_scanned = len(files)
            processed = 0

            for file_path in files:
                try:
                    with file_path.open("r", encoding="utf-8", errors="replace") as f:
                        previous = offsets.get(file_path, 0)
                        f.seek(0, 2)
                        end_pos = f.tell()

                        # If file was rotated/truncated, restart from the beginning.
                        if previous > end_pos:
                            previous = 0

                        f.seek(previous)
                        for raw in f:
                            processed += process_jsonl_line(raw, summary, model_summary)
                        offsets[file_path] = f.tell()
                except OSError:
                    continue

            if processed > 0:
                print(f"[{time.strftime('%H:%M:%S')}] +{processed} request(s)")
                print_summary(
                    summary,
                    model_summary,
                    files_scanned,
                    wh_per_500_tokens=wh_per_500_tokens,
                )
                if hardware is not None:
                    print_hardware_estimate(args.hardware_profile, hardware)
                out_file = write_usage_snapshot(
                    args.log_dir,
                    summary,
                    model_summary,
                    files_scanned,
                    wh_per_500_tokens=wh_per_500_tokens,
                    energy_source=energy_source,
                    hardware=hardware,
                    mode="watch",
                )
                print(f"Log snapshot appended to: {out_file}")
                print()

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")
        print_summary(
            summary,
            model_summary,
            files_scanned,
            wh_per_500_tokens=wh_per_500_tokens,
        )
        if hardware is not None:
            print_hardware_estimate(args.hardware_profile, hardware)
        out_file = write_usage_snapshot(
            args.log_dir,
            summary,
            model_summary,
            files_scanned,
            wh_per_500_tokens=wh_per_500_tokens,
            energy_source=energy_source,
            hardware=hardware,
            mode="watch-stop",
        )
        print(f"Log snapshot appended to: {out_file}")
        return 0


# Purpose: Print agent/model tables plus energy summary to stdout.
# Inputs: summary, model_summary, files_scanned, wh_per_500_tokens.
# Outputs: None.
# Side Effects: Writes text to stdout.
def print_summary(
    summary: dict[str, AgentStats],
    model_summary: dict[str, AgentStats],
    files_scanned: int,
    wh_per_500_tokens: float,
) -> None:
    if not summary:
        print("No Copilot requests found. Check your session path(s).")
        return

    header = (
        f"Scanned {files_scanned} session file(s). "
        "Token counts use real usage data when present; otherwise they are estimated."
    )
    print(header)
    print()

    print(
        f"{'Agent':20} {'Requests':>8} {'Prompt':>10} {'Completion':>12} "
        f"{'Total':>10} {'Actual':>8} {'Estimated':>10}"
    )
    print("-" * 86)

    for agent, stats in sorted(
        summary.items(), key=lambda x: x[1].total_tokens, reverse=True
    ):
        print(
            f"{agent[:20]:20} {stats.requests:8d} {stats.prompt_tokens:10d} "
            f"{stats.completion_tokens:12d} {stats.total_tokens:10d} "
            f"{stats.actual_requests:8d} {stats.estimated_requests:10d}"
        )

    if model_summary:
        print()
        print(
            f"{'Model':30} {'Requests':>8} {'Prompt':>10} {'Completion':>12} "
            f"{'Total':>10} {'Actual':>8} {'Estimated':>10}"
        )
        print("-" * 106)
        for model, stats in sorted(
            model_summary.items(), key=lambda x: x[1].total_tokens, reverse=True
        ):
            print(
                f"{model[:30]:30} {stats.requests:8d} {stats.prompt_tokens:10d} "
                f"{stats.completion_tokens:12d} {stats.total_tokens:10d} "
                f"{stats.actual_requests:8d} {stats.estimated_requests:10d}"
            )

    totals = aggregate_totals(summary)
    energy_wh, energy_kwh = compute_energy(totals.total_tokens, wh_per_500_tokens)
    print()
    print(f"Estimated energy: {energy_wh:.2f} Wh ({energy_kwh:.4f} kWh)")
    print(
        f"Model factor used: {wh_per_500_tokens:g} Wh per 500 tokens "
        "(user-configurable)"
    )


# Purpose: Script entry point for one-shot or watch execution paths.
# Inputs: None.
# Outputs: Process exit code.
# Side Effects: Reads logs, writes snapshots, and prints reports.
def main() -> int:
    args = parse_args()
    hardware = resolve_hardware_profile(args)
    wh_per_500_tokens, energy_source = choose_wh_per_500_tokens(args, hardware)

    if args.watch:
        return stream_summary(args)

    files = discover_session_files(args)

    if not files:
        print("No session files found.")
        print("Try --sessions-dir, --copilot-logs-dir, or --workspace-storage-root.")
        return 1

    summary, model_summary = summarize(files)
    print_summary(
        summary,
        model_summary,
        len(files),
        wh_per_500_tokens=wh_per_500_tokens,
    )
    if hardware is not None:
        print_hardware_estimate(args.hardware_profile, hardware)
    out_file = write_usage_snapshot(
        args.log_dir,
        summary,
        model_summary,
        len(files),
        wh_per_500_tokens=wh_per_500_tokens,
        energy_source=energy_source,
        hardware=hardware,
        mode="oneshot",
    )
    print(f"Log snapshot appended to: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
