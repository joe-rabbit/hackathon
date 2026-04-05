#!/usr/bin/env python3
"""Cross-session user-prompt deduplication: fingerprint, fuzzy + word cosine, log cache candidates."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_DASH = Path(__file__).resolve().parent
if str(_DASH) not in sys.path:
    sys.path.insert(0, str(_DASH))

from agent_token_analyszer import (  # noqa: E402
    extract_content_from_message,
    extract_requests_from_line,
    find_messages_lists,
    iter_json_objects_from_file,
)
from green_prompt import compress_prompt, estimate_tokens  # noqa: E402

# Extra fillers for semantic fingerprint (beyond green_prompt.compress_prompt)
_EXTRA_FILLER = (
    r"(?i)\bcould you\b",
    r"(?i)\bcan you help me\b",
    r"(?i)\bwould you\b",
    r"(?i)\bcould you please\b",
)


def semantic_fingerprint(raw: str) -> str:
    """Normalize whitespace, strip filler, lowercase — stable string for similarity."""
    t = compress_prompt(raw)
    for pat in _EXTRA_FILLER:
        t = re.sub(pat, " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def word_cosine(a: str, b: str) -> float:
    """Cosine similarity on word frequency vectors (bag-of-words)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ca, cb = Counter(a.split()), Counter(b.split())
    if not ca or not cb:
        return 0.0
    dot = sum(ca[w] * cb.get(w, 0) for w in ca)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def fuzzy_ratio(a: str, b: str) -> float:
    """Normalized fuzzy match [0,1] using Python difflib (sequence similarity)."""
    return SequenceMatcher(None, a, b).ratio()


def combined_similarity(fp_a: str, fp_b: str) -> float:
    """Use max(word cosine, sequence ratio) so either strong signal counts (OR-style)."""
    return max(word_cosine(fp_a, fp_b), fuzzy_ratio(fp_a, fp_b))


def extract_user_prompts_from_dict(obj: dict[str, Any]) -> list[str]:
    """Collect user prompt texts from Copilot requests, Cursor lines, or nested messages."""
    out: list[str] = []
    for req in extract_requests_from_line(obj):
        msg = req.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("text"), str):
            t = msg["text"].strip()
            if len(t) >= 2:
                out.append(t)
    if obj.get("role") == "user":
        t = extract_content_from_message(obj).strip()
        if len(t) >= 2:
            out.append(t)
    for ml in find_messages_lists(obj):
        if not isinstance(ml, list):
            continue
        for m in ml:
            if isinstance(m, dict) and m.get("role") == "user":
                t = extract_content_from_message(m).strip()
                if len(t) >= 2:
                    out.append(t)
    return out


@dataclass
class PromptEntry:
    source_file: str
    line_number: int
    ordinal: int
    raw: str


def collect_prompts(input_dir: Path, repo_root: Path) -> list[PromptEntry]:
    entries: list[PromptEntry] = []
    ordinal = 0
    if not input_dir.is_dir():
        return entries

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        suf = path.suffix.lower()
        if suf not in (".jsonl", ".json"):
            continue
        try:
            rel_s = str(path.relative_to(repo_root))
        except ValueError:
            rel_s = str(path)

        if suf == ".jsonl":
            line_no = 0
            with path.open(encoding="utf-8", errors="replace") as f:
                for raw_line in f:
                    line_no += 1
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        obj = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    for p in extract_user_prompts_from_dict(obj):
                        entries.append(PromptEntry(rel_s, line_no, ordinal, p))
                        ordinal += 1
        else:
            obj_line = 0
            for obj in iter_json_objects_from_file(path):
                obj_line += 1
                if not isinstance(obj, dict):
                    continue
                for p in extract_user_prompts_from_dict(obj):
                    entries.append(PromptEntry(rel_s, obj_line, ordinal, p))
                    ordinal += 1

    return entries


def tokens_saved_if_cached_estimate(duplicate_raw: str) -> int:
    """Rough tokens not spent if duplicate had been served from cache (in + out estimate)."""
    inp = estimate_tokens(duplicate_raw)
    return inp + inp  # assume similar completion size to prior ask


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Find near-duplicate user prompts across workspace_chat_logs JSONL."
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        default=_REPO / "workspace_chat_logs",
        help="Directory of JSONL/JSON chat exports (default: ./workspace_chat_logs).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=_REPO / "logs" / "dedup_results.jsonl",
        help="JSONL output path (default: ./logs/dedup_results.jsonl).",
    )
    p.add_argument(
        "--append",
        action="store_true",
        help="Append to output file instead of overwriting (default: overwrite each run).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Min combined similarity [0-1] to flag a pair (default: 0.85).",
    )
    p.add_argument(
        "--min-fingerprint-len",
        type=int,
        default=3,
        help="Skip fingerprints shorter than this (default: 3).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    entries = collect_prompts(input_dir, _REPO)
    if not entries:
        print(f"No user prompts found under {input_dir}")
        print("Add JSONL/JSON chat logs to that directory and re-run.")
        return 1

    fingerprints = [semantic_fingerprint(e.raw) for e in entries]
    n = len(entries)
    pairs_written = 0
    th = max(0.0, min(1.0, args.threshold))

    mode = "a" if args.append else "w"
    with out_path.open(mode, encoding="utf-8") as out_f:
        for i in range(n):
            for j in range(i + 1, n):
                fi, fj = fingerprints[i], fingerprints[j]
                if len(fi) < args.min_fingerprint_len or len(fj) < args.min_fingerprint_len:
                    continue
                sim = combined_similarity(fi, fj)
                if sim < th:
                    continue
                orig, dup = entries[i], entries[j]
                record = {
                    "original_prompt": orig.raw,
                    "duplicate_prompt": dup.raw,
                    "similarity_score": round(sim, 6),
                    "tokens_saved_if_cached": tokens_saved_if_cached_estimate(dup.raw),
                    "source_files": sorted({orig.source_file, dup.source_file}),
                }
                out_f.write(json.dumps(record, ensure_ascii=True) + "\n")
                pairs_written += 1

    print(
        f"Scanned {n} user prompts from {input_dir}. "
        f"Wrote {pairs_written} near-duplicate pair(s) (similarity >= {th}) to {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
