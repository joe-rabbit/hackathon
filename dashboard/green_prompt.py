"""Conservative prompt compression — only objective waste (whitespace, filler, dup context).

Does not rewrite user intent; returns a before/after for transparency.
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_p = Path(__file__).resolve().parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

from carbon_constants import carbon_saved_g  # noqa: E402

# Polite filler that can usually be dropped without changing task semantics
_FILLER_PATTERNS = (
    r"(?i)\bplease\b",
    r"(?i)\bcould you kindly\b",
    r"(?i)\bkindly\b",
    r"(?i)\bi was wondering if\b",
    r"(?i)\bi would like to ask\b",
    r"(?i)\bif you could\b",
    r"(?i)\bthank you in advance\b",
    r"(?i)\bthanks in advance\b",
)


@dataclass(frozen=True)
class GreenPromptResult:
    original: str
    compressed: str
    original_tokens_est: int
    compressed_tokens_est: int
    tokens_saved: int
    efficiency_ratio: float  # compressed / original (0–1]; 1 = no savings

    def carbon_saved_g(self, tier: str) -> float:
        return carbon_saved_g(self.tokens_saved, tier)


def estimate_tokens(text: str) -> int:
    if not text or not text.strip():
        return 0
    return int(math.ceil(len(text) / 4.0))


def _collapse_ws(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_filler(text: str) -> str:
    out = text
    for pat in _FILLER_PATTERNS:
        out = re.sub(pat, " ", out)
    return _collapse_ws(out)


def _dedupe_paragraphs(text: str) -> str:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    seen: set[str] = set()
    kept: list[str] = []
    for p in paras:
        key = " ".join(p.split())
        if key in seen:
            continue
        seen.add(key)
        kept.append(p)
    return "\n\n".join(kept)


def compress_prompt(text: str) -> str:
    if not text:
        return ""
    t = _collapse_ws(text)
    t = _strip_filler(t)
    t = _dedupe_paragraphs(t)
    return t


def green_prompt(text: str, tier: str = "laptop") -> GreenPromptResult:
    original = text
    compressed = compress_prompt(text)
    o_est = estimate_tokens(original)
    c_est = estimate_tokens(compressed)
    saved = max(0, o_est - c_est)
    ratio = (c_est / o_est) if o_est > 0 else 1.0
    return GreenPromptResult(
        original=original,
        compressed=compressed,
        original_tokens_est=o_est,
        compressed_tokens_est=c_est,
        tokens_saved=saved,
        efficiency_ratio=ratio,
    )


def summarize_batch_savings(
    texts: list[str], tier: str = "laptop"
) -> dict[str, float | int]:
    """Aggregate compression stats for multiple prompts (e.g. last user messages)."""
    total_o = 0
    total_c = 0
    total_saved = 0
    for t in texts:
        r = green_prompt(t, tier=tier)
        total_o += r.original_tokens_est
        total_c += r.compressed_tokens_est
        total_saved += r.tokens_saved
    ratio = (total_c / total_o) if total_o > 0 else 1.0
    return {
        "tokens_original_est": total_o,
        "tokens_compressed_est": total_c,
        "tokens_saved": total_saved,
        "efficiency_ratio": round(ratio, 4),
        "carbon_saved_g": round(carbon_saved_g(total_saved, tier), 6),
    }
