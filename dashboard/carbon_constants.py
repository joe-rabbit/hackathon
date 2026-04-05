"""Defensible carbon-per-token factors for hackathon demos (grams CO2 per token).

Rough model: power draw / throughput → energy per token × grid intensity proxy.
"""

from __future__ import annotations

# Cloud GPU (A100-class) ≈ 300W, ~100 tokens/sec
CLOUD_CARBON_PER_TOKEN_G = 0.0027

# Raspberry Pi ≈ 5W, ~10 tokens/sec
PI_CARBON_PER_TOKEN_G = 0.00042

# Laptop ≈ 45W, ~50 tokens/sec
LAPTOP_CARBON_PER_TOKEN_G = 0.00075

TIER_ALIASES = {
    "cloud": CLOUD_CARBON_PER_TOKEN_G,
    "a100": CLOUD_CARBON_PER_TOKEN_G,
    "gpu": CLOUD_CARBON_PER_TOKEN_G,
    "pi": PI_CARBON_PER_TOKEN_G,
    "edge": PI_CARBON_PER_TOKEN_G,
    "raspberry": PI_CARBON_PER_TOKEN_G,
    "laptop": LAPTOP_CARBON_PER_TOKEN_G,
    "local": LAPTOP_CARBON_PER_TOKEN_G,
}


def carbon_per_token_g(tier: str) -> float:
    key = (tier or "laptop").strip().lower()
    return TIER_ALIASES.get(key, LAPTOP_CARBON_PER_TOKEN_G)


def carbon_saved_g(tokens_saved: int, tier: str) -> float:
    if tokens_saved <= 0:
        return 0.0
    return float(tokens_saved) * carbon_per_token_g(tier)


# EPA-ish: average passenger vehicle ~400 g CO2 / mile (order of magnitude for demos)
G_CO2E_PER_VEHICLE_MILE = 400.0

# Rough offset: ~20 kg CO2 / tree / year → ~20_000_000 mg; per day ~55 g/tree/day (very rough)
G_CO2E_PER_TREE_DAY = 55.0


def miles_equivalent(g_co2e: float) -> float:
    if g_co2e <= 0:
        return 0.0
    return g_co2e / G_CO2E_PER_VEHICLE_MILE


def trees_per_day_equivalent(g_co2e: float) -> float:
    if g_co2e <= 0:
        return 0.0
    return g_co2e / G_CO2E_PER_TREE_DAY
