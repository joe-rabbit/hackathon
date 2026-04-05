#!/usr/bin/env python3
"""Prompt optimizer for Mochi.

Intercepts prompts before model calls, applies conservative rewrites, and logs
prompt-efficiency events for later Influx ingestion.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from green_prompt import estimate_tokens  # noqa: E402

GOLD_PROMPTS_PATH = REPO_ROOT / "gold_prompts.json"
PROMPT_EFFICIENCY_LOG_PATH = REPO_ROOT / "logs" / "prompt_efficiency_log.jsonl"
CLOUD_CARBON_PER_TOKEN_KG = 0.0000027
CLOUD_CARBON_PER_TOKEN_G = CLOUD_CARBON_PER_TOKEN_KG * 1000.0
DEFAULT_MAX_TOKENS = 1024

REDUNDANT_INSTRUCTION_PATTERNS = (
    (r"(?i)\bmake sure to\b", ""),
    (r"(?i)\bdon't forget to\b", ""),
    (r"(?i)\bdo not forget to\b", ""),
    (r"(?i)\bbe sure to\b", ""),
    (r"(?i)\bremember to\b", ""),
)

FILLER_PATTERNS = (
    r"(?i)\bplease\b",
    r"(?i)\bcould you\b",
    r"(?i)\bcould you kindly\b",
    r"(?i)\bcan you help me\b",
    r"(?i)\bi was wondering if\b",
    r"(?i)\bwould you\b",
    r"(?i)\bthanks in advance\b",
    r"(?i)\bthank you in advance\b",
)


@dataclass(frozen=True)
class PromptEfficiencyEvent:
    optimization_type: str
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    carbon_saved_g: float
    task_type: str
    original_prompt: str
    optimized_prompt: str
    original_system_prompt: str
    optimized_system_prompt: str
    max_tokens_before: int | None = None
    max_tokens_after: int | None = None


@dataclass(frozen=True)
class PromptOptimizationResult:
    original_prompt: str
    optimized_prompt: str
    original_system_prompt: str
    optimized_system_prompt: str
    task_type: str
    max_tokens: int | None
    events: list[PromptEfficiencyEvent] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.events)


def _collapse_ws(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_fillers(text: str) -> str:
    out = text
    for pat in FILLER_PATTERNS:
        out = re.sub(pat, " ", out)
    return _collapse_ws(out)


def _collapse_redundant_instructions(text: str) -> str:
    out = text
    for pat, repl in REDUNDANT_INSTRUCTION_PATTERNS:
        out = re.sub(pat, repl, out)
    return _collapse_ws(out)


def _system_fingerprint(text: str) -> str:
    return _collapse_ws(text).lower()


def load_gold_prompts(path: Path = GOLD_PROMPTS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def classify_task_type(prompt: str, gold_rule: dict[str, Any] | None = None) -> str:
    if gold_rule and isinstance(gold_rule.get("task_type"), str):
        return gold_rule["task_type"]
    p = prompt.lower()
    if any(k in p for k in ("classify", "label", "sentiment", "spam or ham", "category")):
        return "classification"
    if any(k in p for k in ("summarize", "summary", "tl;dr", "condense")):
        return "summarization"
    if any(
        k in p
        for k in (
            "write code",
            "write a function",
            "python function",
            "implement",
            "refactor",
            "script",
            "program",
            "code",
            "tsx",
            "jsx",
            "bug in",
        )
    ):
        return "code_generation"
    return "general"


def ceiling_for_task_type(task_type: str) -> int | None:
    if task_type == "classification":
        return 50
    if task_type == "summarization":
        return 200
    if task_type == "code_generation":
        return 500
    return None


def maybe_apply_gold_rewrite(prompt: str, gold_prompts: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    for rule in gold_prompts:
        patterns = rule.get("patterns")
        rewrite = rule.get("rewrite")
        if not isinstance(patterns, list) or not isinstance(rewrite, str):
            continue
        for pat in patterns:
            if isinstance(pat, str) and re.search(pat, prompt, flags=re.IGNORECASE):
                rewritten = _collapse_ws(rewrite)
                if estimate_tokens(rewritten) <= estimate_tokens(prompt):
                    return rewritten, rule
                return prompt, None
    return prompt, None


def _wants_explanation(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in ("explain", "why", "walk me through", "with comments", "commented", "step by step"))


def maybe_add_implicit_constraints(prompt: str, task_type: str) -> str:
    p = prompt.rstrip(" .;")
    lower = p.lower()
    if task_type == "code_generation" and not _wants_explanation(lower):
        additions = []
        if "code only" not in lower:
            additions.append("code only")
        if (
            "no preamble" not in lower
            and "no explanation" not in lower
            and "code only" not in lower
        ):
            additions.append("no preamble")
        if additions:
            p = f"{p}. {'; '.join(additions)}"
    elif task_type == "classification":
        additions = []
        if "label only" not in lower:
            additions.append("label only")
        if "no preamble" not in lower:
            additions.append("no preamble")
        if additions:
            p = f"{p}. {'; '.join(additions)}"
    elif task_type == "summarization":
        additions = []
        if "summary only" not in lower:
            additions.append("summary only")
        if "no preamble" not in lower:
            additions.append("no preamble")
        if additions:
            p = f"{p}. {'; '.join(additions)}"
    return _collapse_ws(p)


def _make_event(
    optimization_type: str,
    before_prompt: str,
    after_prompt: str,
    before_system_prompt: str,
    after_system_prompt: str,
    task_type: str,
    max_tokens_before: int | None = None,
    max_tokens_after: int | None = None,
    tokens_saved_override: int | None = None,
) -> PromptEfficiencyEvent:
    before_tokens = estimate_tokens(before_prompt) + estimate_tokens(before_system_prompt)
    after_tokens = estimate_tokens(after_prompt) + estimate_tokens(after_system_prompt)
    saved = max(0, before_tokens - after_tokens)
    if tokens_saved_override is not None:
        saved = max(0, tokens_saved_override)
    return PromptEfficiencyEvent(
        optimization_type=optimization_type,
        original_tokens=before_tokens,
        optimized_tokens=after_tokens,
        tokens_saved=saved,
        carbon_saved_g=round(saved * CLOUD_CARBON_PER_TOKEN_G, 6),
        task_type=task_type,
        original_prompt=before_prompt,
        optimized_prompt=after_prompt,
        original_system_prompt=before_system_prompt,
        optimized_system_prompt=after_system_prompt,
        max_tokens_before=max_tokens_before,
        max_tokens_after=max_tokens_after,
    )


def optimize_prompt(
    prompt: str,
    *,
    system_prompt: str = "",
    last_system_prompt: str = "",
    gold_prompts_path: Path = GOLD_PROMPTS_PATH,
    dry_run: bool = False,
    log_path: Path = PROMPT_EFFICIENCY_LOG_PATH,
    source: str = "app",
) -> PromptOptimizationResult:
    gold_prompts = load_gold_prompts(gold_prompts_path)
    current_prompt = _collapse_ws(prompt)
    current_system_prompt = _collapse_ws(system_prompt)
    events: list[PromptEfficiencyEvent] = []
    base_task_type = classify_task_type(current_prompt)

    before = current_prompt
    after = _collapse_redundant_instructions(_strip_fillers(current_prompt))
    if after != before:
        events.append(
            _make_event(
                "filler_removal",
                before,
                after,
                current_system_prompt,
                current_system_prompt,
                base_task_type,
            )
        )
        current_prompt = after

    rewritten_prompt, matched_rule = maybe_apply_gold_rewrite(current_prompt, gold_prompts)
    task_type = classify_task_type(current_prompt, matched_rule)
    constrained_prompt = maybe_add_implicit_constraints(rewritten_prompt, task_type)
    if constrained_prompt != current_prompt:
        events.append(
            _make_event(
                "rewrite",
                current_prompt,
                constrained_prompt,
                current_system_prompt,
                current_system_prompt,
                task_type,
            )
        )
        current_prompt = constrained_prompt

    if current_system_prompt and last_system_prompt:
        if _system_fingerprint(current_system_prompt) == _system_fingerprint(last_system_prompt):
            before_system = current_system_prompt
            current_system_prompt = ""
            events.append(
                _make_event(
                    "dedup",
                    current_prompt,
                    current_prompt,
                    before_system,
                    current_system_prompt,
                    task_type,
                )
            )

    max_tokens = ceiling_for_task_type(task_type)
    if max_tokens is not None and max_tokens < DEFAULT_MAX_TOKENS:
        events.append(
            _make_event(
                "ceiling",
                current_prompt,
                current_prompt,
                current_system_prompt,
                current_system_prompt,
                task_type,
                max_tokens_before=DEFAULT_MAX_TOKENS,
                max_tokens_after=max_tokens,
                tokens_saved_override=DEFAULT_MAX_TOKENS - max_tokens,
            )
        )

    result = PromptOptimizationResult(
        original_prompt=prompt,
        optimized_prompt=current_prompt,
        original_system_prompt=system_prompt,
        optimized_system_prompt=current_system_prompt,
        task_type=task_type,
        max_tokens=max_tokens,
        events=events,
    )
    if not dry_run:
        log_prompt_efficiency(result, log_path=log_path, source=source)
    return result


def log_prompt_efficiency(
    result: PromptOptimizationResult,
    *,
    log_path: Path = PROMPT_EFFICIENCY_LOG_PATH,
    source: str = "app",
) -> None:
    if not result.events:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        for event in result.events:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "optimization_type": event.optimization_type,
                "task_type": event.task_type,
                "original_tokens": event.original_tokens,
                "optimized_tokens": event.optimized_tokens,
                "tokens_saved": event.tokens_saved,
                "carbon_saved_g": event.carbon_saved_g,
                "original_prompt": event.original_prompt,
                "optimized_prompt": event.optimized_prompt,
                "original_system_prompt": event.original_system_prompt,
                "optimized_system_prompt": event.optimized_system_prompt,
                "max_tokens_before": event.max_tokens_before,
                "max_tokens_after": event.max_tokens_after,
            }
            f.write(json.dumps(record, ensure_ascii=True) + "\n")


def format_diff(before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    out = "\n".join(diff).strip()
    return out or "(no textual diff)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimize a prompt using gold rewrites and conservative constraints."
    )
    parser.add_argument("--prompt", required=True, help="Prompt text to optimize.")
    parser.add_argument("--system-prompt", default="", help="Optional system prompt.")
    parser.add_argument(
        "--last-system-prompt",
        default="",
        help="Optional previous turn system prompt for dedup testing.",
    )
    parser.add_argument(
        "--gold-prompts",
        type=Path,
        default=GOLD_PROMPTS_PATH,
        help="Path to gold_prompts.json.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=PROMPT_EFFICIENCY_LOG_PATH,
        help="Where prompt efficiency JSONL events are written.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show before/after diff without writing optimization logs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = optimize_prompt(
        args.prompt,
        system_prompt=args.system_prompt,
        last_system_prompt=args.last_system_prompt,
        gold_prompts_path=args.gold_prompts,
        dry_run=args.dry_run,
        log_path=args.log_path,
        source="cli",
    )
    print(f"Task type: {result.task_type}")
    print(f"Max tokens: {result.max_tokens}")
    print("Applied optimizations:", ", ".join(e.optimization_type for e in result.events) or "none")
    print()
    print("Prompt diff:")
    print(format_diff(result.original_prompt, result.optimized_prompt))
    if result.original_system_prompt or result.optimized_system_prompt:
        print()
        print("System prompt diff:")
        print(format_diff(result.original_system_prompt, result.optimized_system_prompt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
