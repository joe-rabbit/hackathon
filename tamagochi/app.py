"""Mochi Terminal UI - Nyan Cat Style Animated Hero.

Mochi flies across the screen with a rainbow trail, pixel sparkles, and
full Nyan Cat-inspired energy. Drop-in replacement for the hero rendering.
"""

import os
import sys
import time
import math
import random
import re
import json
import glob
import subprocess
import threading
import queue
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from types import SimpleNamespace
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# Add project root to sys.path to allow importing from the parent directory
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from prompt_optimizer import optimize_prompt

# ═══════════════════════════════════════════════════════════════════════════════
# COLOR PALETTE
# ═══════════════════════════════════════════════════════════════════════════════

RESET = "\033[0m"

BG_MAIN = "17"
BG_SURFACE = "234"
BG_SURFACE2 = "235"
BORDER_COLOR = "238"

TEXT_MAIN = "255"
TEXT_DIM = "248"
TEXT_DIMMER = "240"

GREEN = "114"
PINK = "211"
HOT = "204"
MINT = "158"
YELLOW = "227"

MOCHI_BODY = "186"
MOCHI_DARK = "236"
MOCHI_CHEEK = "211"
MOCHI_SHINE = "231"
MOCHI_MOUTH = "210"
MOCHI_ARMS = "228"

DASHBOARD_URL = "http://localhost:8086"
DEVICE_STATUS_PORT = 8000
CONNECTED_DEVICES_FILE = Path(__file__).with_name("connected_devices.json")
USAGE_SNAPSHOT_FILE = REPO_ROOT / "logs" / "copilot_usage_log.jsonl"
PROMPT_EFFICIENCY_LOG_FILE = REPO_ROOT / "logs" / "prompt_efficiency_log.jsonl"
INGEST_HEARTBEAT_FILE = REPO_ROOT / "logs" / "influx_ingest_heartbeat.json"
ANALYZER_SCRIPT = REPO_ROOT / "dashboard" / "agent_token_analyszer.py"
INFLUX_PUSH_SCRIPT = REPO_ROOT / "dashboard" / "push_usage_to_influx.py"

# Optimize policy constants for O hotkey
CO2_THRESHOLD_KG = 0.08
GRID_KG_CO2E_PER_KWH = 0.384
WH_PER_500_TOKENS = 15.0
AUTO_OPTIMIZE_INTERVAL_S = 30.0
AUTO_OPTIMIZE_COOLDOWN_S = 90.0
EMISSION_REFRESH_INTERVAL_S = 10.0

RAINBOW_COLORS = ["196", "208", "226", "46", "27", "57", "129"]
SPARKLE_CHARS = ["✦", "✧", "★", "☆", "·", "✸", "✺", "⋆", "*"]

TOKEN_KEY_SETS = (
    ("promptTokens", "completionTokens", "totalTokens"),
    ("prompt_tokens", "completion_tokens", "total_tokens"),
    ("inputTokens", "outputTokens", "totalTokens"),
    ("input_tokens", "output_tokens", "total_tokens"),
)

# ═══════════════════════════════════════════════════════════════════════════════
# ANSI UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def fg(color: str) -> str:
    return f"\033[38;5;{color}m"

def bg(color: str) -> str:
    return f"\033[48;5;{color}m"

def bold() -> str:
    return "\033[1m"

def clear_screen() -> str:
    return "\033[2J\033[H"

def move_cursor(row: int, col: int) -> str:
    return f"\033[{row};{col}H"

def hide_cursor() -> str:
    return "\033[?25l"

def show_cursor() -> str:
    return "\033[?25h"

def enter_alt_screen() -> str:
    return "\033[?1049h"

def exit_alt_screen() -> str:
    return "\033[?1049l"

def clear_line() -> str:
    return "\033[2K"

def get_terminal_size() -> tuple[int, int]:
    try:
        size = os.get_terminal_size()
        return size.lines, size.columns
    except:
        return 24, 80


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK DATA
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_AGENTS = [
    {"name": "Camera Vision", "cpu": 85, "mem": 380, "tok": 1997, "status": "HOT",
     "latency": 540, "temp": 61.7, "optimizer": "compressing"},
    {"name": "NLP Process", "cpu": 39, "mem": 280, "tok": 677, "status": "OK",
     "latency": 210, "temp": 45.2, "optimizer": "none"},
    {"name": "Object Detect", "cpu": 38, "mem": 172, "tok": 523, "status": "OK",
     "latency": 180, "temp": 44.8, "optimizer": "batched"},
    {"name": "Request Router", "cpu": 19, "mem": 77, "tok": 220, "status": "OK",
     "latency": 50, "temp": 38.1, "optimizer": "none"},
    {"name": "Audio Process", "cpu": 49, "mem": 231, "tok": 592, "status": "OK",
     "latency": 260, "temp": 48.3, "optimizer": "none"},
]

MOCK_ALERTS = [
    "camera-agent token spike detected",
    "camera-agent CPU above hot threshold",
]


# ═══════════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════════

CAT_MESSAGES = {
    "idle":      ["meow~", "purrrr...", "*yawn*", "nyaa~", "...", "*blink*", "uwu", "~nya", "*purr*", "hmm?", "♪♫", "*tail wag*", "?_?"],
    "happy":     ["nyaa~!!", "purrrr~", "♥", "uwu", "*happy squirm*", "meow!!"],
    "thinking":  ["hmm...", "...", "calculating...", "*stare*", "processing~"],
    "warning":   ["!!!", "*ears back*", "hisss!", "danger!", "mrrp?!"],
    "sad":       ["...", "*sigh*", "meh", "lonely...", "*droopy ears*"],
    "celebrate": ["NYAA~!", "✦✦✦", "yay!!", "purrr!!", "*spin*", "meow!!"],
    "sleepy":    ["zzz...", "*yawn*", "tired...", "...zzz", "zz~"],
    "sleeping":  ["zzz...", "...zzz", "zz~", "Zzz"],
    "excited":   ["!!", "nyaa!!", "*zoom*", "yay!!!", "♥♥"],
    "treat":     ["nom nom!", "yummy~", "*chomp*", "more plz", "mew!!"],
    "pet":       ["purrr~", "♥", "uwu", "*leans in*", "soft..."],
}

CarbonTask = dict[str, object]


@dataclass
class AppState:
    running: bool = True
    input_buffer: str = ""
    transcript: list = field(default_factory=list)
    transcript_scroll: int = 0
    mood: str = "idle"
    mood_timer: int = 0
    frame: int = 0
    blink_until: float = 0.0
    jump_until: float = 0.0
    last_resize: tuple = (0, 0)
    model_name: str = "gemma3:1b"
    backend_status: str = "connected"
    mode: str = "mock"
    current_message: str = "meow~"
    message_timer: int = 0
    tail_frame: int = 0
    # Walking animation
    walk_until: float = 0.0
    walk_offset: int = 0
    walk_direction: int = 1  # 1 for right, -1 for left
    next_auto_optimize_check: float = 0.0
    auto_optimize_cooldown_until: float = 0.0
    last_system_prompt_sent: str = ""
    known_devices: list[str] = field(default_factory=list)
    latest_co2_kg: float = 0.0
    latest_tokens: int = 0
    latest_signal_source: str = "none"
    eco_level: int = 1
    flower_stage: str = "seed"
    next_emission_refresh: float = 0.0
    prompt_tokens_saved_recent: int = 0
    prompt_carbon_saved_recent_g: float = 0.0
    emission_poll_inflight: bool = False
    llm_inflight: bool = False
    optimization_workflow_inflight: bool = False
    last_workflow_status: str = "idle"
    last_workflow_error: str = ""
    last_workflow_run_at: float = 0.0
    carbon_threshold_percentile: float = 25.0
    carbon_max_delay_s: float = 300.0
    carbon_task_queue: list[CarbonTask] = field(default_factory=list)
    carbon_allocation_history: list[CarbonTask] = field(default_factory=list)
    last_device_rankings: list[dict] = field(default_factory=list)
    popup_title: str = ""
    popup_detail: str = ""
    popup_kind: str = "info"
    popup_until: float = 0.0
    life_points: int = 35
    life_points_max: int = 100
    event_queue: queue.Queue = field(default_factory=queue.Queue)


# ═══════════════════════════════════════════════════════════════════════════════
# PIXEL ART CAT - 28x28
# ═══════════════════════════════════════════════════════════════════════════════

CAT_PIXEL_DATA = [
    "............................",
    ".........................KK.",
    ".......................GKAK.",
    "........KKKK..........GGAAK.",
    ".........GAGGG.......GAAAAK.",
    ".........GAAAAGGGGGGKAAAAAK.",
    ".........GAAAAAAAAAAAAAAAAG.",
    ".........GAKKGGGAAAAAGGGKAG.",
    ".........GKKWKGGGGAAGWGGGGK.",
    ".........GKWWWGGYKAGWWWGYYG.",
    "........GAKWWGGGYGAGWWGGGYG.",
    "........GAGGGGGGYGAGGGGGGYG.",
    "........GPGYGGGYYGAGGGGGGYP.",
    "........GPPGYYYYGAAGGYYYYPP.",
    "........GAAAGGGKAAAAGGGGGPG.",
    "........GAAAAKAAAAAAAAGAAG..",
    ".........GGGGAAAAAAAAAAAK...",
    "...........WWKGGGGGKKGGG....",
    ".............KKKKYYKKKKK....",
    "............KKKKKYYKKKKK....",
    "............KAAAAAAAAAAAK...",
    "...........KAAAAAAAAAAAAK...",
    ".........KKAAAAAAAAAAAAAAK..",
    ".........KAAAAAAAAAAAAAAAK..",
    ".........KAKAAAKAAAKAAAKAKK.",
    "........KKAKAAAKAAAKAAAKAAK.",
    "........KKAKAAAKAAAKAAAKAAK.",
    "........KAAKAAAKAAAKAAAKAAK.",
]

# Pixel color map → ANSI 256 background codes
CAT_COLORS = {
    '.': None,
    'K': "\033[48;5;16m",    # black
    'G': "\033[48;5;234m",   # dark gray (#121212)
    'A': "\033[48;5;239m",   # gray (#454545)
    'W': "\033[48;5;231m",   # white  (normal eye)
    'Y': "\033[48;5;220m",   # yellow (#ffc231)
    'P': "\033[48;5;132m",   # pink (#76374c)
    # Expression overrides (added below)
    'C': "\033[48;5;175m",   # rosy cheek pink
    'H': "\033[48;5;196m",   # heart red  (excited eye)
    'Z': "\033[48;5;111m",   # zzz blue   (sleep pixel)
    'S': "\033[48;5;239m",   # closed eye = dark gray
}

CAT_SPRITE_WIDTH = 28
CAT_SPRITE_HEIGHT = 14


# Eye pixel positions (row, col) in the SAMPLED (every-2nd-row) grid
# Sampled rows = original rows 0,2,4,6,8,10,12,14,16,18,20,22,24,26
# Left eye cluster:  sampled rows 4-5, cols 11-13
# Right eye cluster: sampled rows 4-5, cols 20-22
EYE_LEFT  = {(4,11),(4,12),(4,13),(5,10),(5,11),(5,12)}
EYE_RIGHT = {(4,20),(4,21),(4,22),(5,19),(5,20),(5,21)}

# Cheek positions (sampled rows 6, cols 9 and 19  — just inside the face)
CHEEK_LEFT  = {(6,9),(6,10)}
CHEEK_RIGHT = {(6,19),(6,20)}


def _get_eye_pixel(mood: str, blinking: bool, side: str) -> str:
    """Return the pixel character to use for eye cells based on mood/blink."""
    if blinking or mood in ("sleepy", "sleeping"):
        return 'S'   # closed / dark gray line
    if mood == "excited" or mood == "celebrate":
        return 'H'   # heart / red  (bright)
    if mood == "sad":
        return 'S'   # sad eyes closed slightly
    # default: normal white
    return 'W'


def get_cat_frame_data(mood: str, blinking: bool, frame: int, tail_frame: int = 0) -> list[str]:
    """
    Build the 14-row sampled pixel grid with:
      - mood-driven eye expression
      - rosy cheeks (happy / celebrate / excited)
      - zzz pixel in top-right when sleeping
      - tail wag animation
    """
    rows = [list(CAT_PIXEL_DATA[i]) for i in range(0, 28, 2)]   # 14 rows, each a list

    # ── Eye expression ────────────────────────────────────────────────────────
    eye_pixel = _get_eye_pixel(mood, blinking, "left")
    for (r, c) in EYE_LEFT:
        if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
            if rows[r][c] == 'W':
                rows[r][c] = eye_pixel
    for (r, c) in EYE_RIGHT:
        if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
            if rows[r][c] == 'W':
                rows[r][c] = eye_pixel

    # ── Rosy cheeks ───────────────────────────────────────────────────────────
    if mood in ("happy", "celebrate", "excited", "pet", "treat"):
        for (r, c) in CHEEK_LEFT | CHEEK_RIGHT:
            if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
                if rows[r][c] == 'A':   # only paint over the gray face body
                    rows[r][c] = 'C'

    # ── Sleeping Zzz above the cat's head ────────────────────────────────────
    if mood == "sleeping":
        zzz_phase = (frame // 20) % 3
        # Place zzz above the cat's head (around column 13-15, starting from row 0)
        z_positions = [
            (0, 13),  # First z
            (0, 15),  # Second z (if phase >= 1)  
            (1, 14),  # Third z (if phase >= 2)
        ]
        for i in range(min(zzz_phase + 1, 3)):
            r, c = z_positions[i]
            if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
                rows[r][c] = 'Z'

    # ── Tail wag ──────────────────────────────────────────────────────────────
    tail_phase = tail_frame % 4
    # Convert rows back to strings for tail manipulation (only top rows)
    str_rows = ["".join(r) for r in rows]

    if tail_phase == 1:
        str_rows[0] = str_rows[0][:24] + "KK.."
        str_rows[1] = str_rows[1][:23] + "GKAK."
    elif tail_phase == 2:
        str_rows[0] = str_rows[0][:25] + "K.."
        str_rows[1] = str_rows[1][:24] + "KAK."
    elif tail_phase == 3:
        str_rows[0] = str_rows[0][:26] + "K."
        str_rows[1] = str_rows[1][:25] + "KK."

    return str_rows


def load_cat_from_css(html_path=None):
    """Parse CSS box-shadow and return pixel dict."""
    if html_path is None:
        html_path = os.path.join(os.path.dirname(__file__), 'cat.html')
    try:
        with open(html_path, 'r') as f:
            html = f.read()
    except Exception:
        return {}
    
    match = re.search(r'box-shadow:\s*(.*?);', html, re.DOTALL)
    if not match:
        return {}
    box_shadow = match.group(1)
    
    pattern = r'(\d+)px\s+(\d+)px\s+(#[0-9a-fA-F]+|rgb\([^)]+\)|transparent|white)'
    matches = re.findall(pattern, box_shadow)
    
    pixels = {}
    for x_str, y_str, color in matches:
        x, y = int(x_str), int(y_str)
        
        if color == 'transparent':
            continue
        elif color == 'white':
            r, g, b = 255, 255, 255
        elif color.startswith('#'):
            color = color.lstrip('#')
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
        elif color.startswith('rgb'):
            nums = re.findall(r'\d+', color)
            r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
        else:
            continue
        
        if y not in pixels:
            pixels[y] = {}
        pixels[y][x] = (r, g, b)
    
    return pixels

_CSS_PIXELS = None

# Mochi Animation Overrides
_C = (220, 130, 150) # rosy cheek pink
_H = (220, 40, 40)   # heart red
_Z = (130, 170, 230) # zzz blue
_S = (40,  40,  40)  # closed-eye dark gray

EYE_L = {(8,11),(8,12),(9,11),(9,12),(9,13),(10,11),(10,12)}
EYE_R = {(8,21),(9,20),(9,21),(9,22),(10,20),(10,21)}
CHEEK_L = {(12,9),(13,9),(13,10)}
CHEEK_R = {(12,26),(13,25),(13,26)}

def render_mochi_sprite(mood: str, blinking: bool, frame: int, tail_frame: int = 0) -> tuple[list[str], int]:
    global _CSS_PIXELS
    if _CSS_PIXELS is None:
        _CSS_PIXELS = load_cat_from_css()
    
    pixels = _CSS_PIXELS
    if not pixels:
        return ["  Cat HTML not found  "], 20

    max_y = max(pixels.keys()) if pixels else 0
    max_x = max(max(row.keys()) for row in pixels.values()) if pixels else 0
    
    # ── MUTATE PIXELS FOR ANIMATION ──
    rendered_pixels = {}
    for y in range(max_y + 1):
        rendered_pixels[y] = {}
        if y in pixels:
            for x in pixels[y]:
                rendered_pixels[y][x] = pixels[y][x]
    
    # Eyes
    if blinking or mood in ("sleepy", "sleeping", "sad"):
        eye_color = _S
    elif mood in ("excited", "celebrate"):
        eye_color = _H
    else:
        eye_color = (255, 255, 255)
        
    for r, c in EYE_L | EYE_R:
        if r in rendered_pixels and c in rendered_pixels[r]:
            if rendered_pixels[r][c] == (255, 255, 255):
                rendered_pixels[r][c] = eye_color

    # Cheeks
    if mood in ("happy", "celebrate", "excited", "pet", "treat"):
        for r, c in CHEEK_L | CHEEK_R:
            if r in rendered_pixels and c in rendered_pixels[r]:
                if rendered_pixels[r][c] not in ((255, 255, 255), (0, 0, 0)):
                    rendered_pixels[r][c] = _C

    # Sleeping Zzz
    if mood == "sleeping":
        zzz_phase = (frame // 20) % 4
        zzz_pos = [(0, 9), (1, 7), (2, 5)]
        for i in range(min(zzz_phase, 3)):
            r, c = zzz_pos[i]
            if r not in rendered_pixels: rendered_pixels[r] = {}
            rendered_pixels[r][c] = _Z
            
    # ── RENDER WITH HALF-BLOCKS ──
    lines = []
    for y in range(0, max_y + 1, 2):
        line = ""
        for x in range(max_x + 1):
            top_p = rendered_pixels.get(y, {}).get(x)
            bot_p = rendered_pixels.get(y + 1, {}).get(x)
            
            if top_p and bot_p:
                tr, tg, tb = top_p
                br, bg, bb = bot_p
                line += f"\033[38;2;{tr};{tg};{tb}m\033[48;2;{br};{bg};{bb}m▀\033[0m"
            elif top_p:
                tr, tg, tb = top_p
                line += f"\033[38;2;{tr};{tg};{tb}m▀\033[0m"
            elif bot_p:
                br, bg, bb = bot_p
                line += f"\033[38;2;{br};{bg};{bb}m▄\033[0m"
            else:
                line += " "
        lines.append(line)
    
    return lines, max_x + 1





# ═══════════════════════════════════════════════════════════════════════════════
# HERO RENDERER - Simple centered cat
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero_nyan(state: AppState, width: int, height: int) -> list[str]:
    """Render cat centered in the screen."""
    now = time.time()
    blinking = now < state.blink_until

    # Tail wag cadence
    if state.frame % 8 == 0:
        state.tail_frame = (state.tail_frame + 1) % 4

    sprite_lines, sw = render_mochi_sprite(state.mood, blinking, state.frame, state.tail_frame)
    
    SPRITE_COLS = sw
    SPRITE_ROWS = len(sprite_lines)
    HERO_HEIGHT = max(SPRITE_ROWS + 6, min(30, height // 3))
    
    # Cat positioning - center (with walking animation)
    cat_x = (width - SPRITE_COLS) // 2
    cat_y = (HERO_HEIGHT - SPRITE_ROWS) // 2
    
    # Walking animation
    if now < state.walk_until:
        # Calculate walk progress (0.0 to 1.0 over 3 seconds)
        walk_progress = 1.0 - (state.walk_until - now) / 3.0
        
        if walk_progress < 0.5:
            state.walk_offset = int(walk_progress * 2 * 8)
            state.walk_direction = 1
        else:
            reverse_progress = (walk_progress - 0.5) * 2
            state.walk_offset = int(8 * (1.0 - reverse_progress))
            state.walk_direction = -1
        
        cat_x += state.walk_offset
    else:
        # Walking finished, reset
        state.walk_offset = 0
    
    # Jump animation
    jump_offset = 0
    if now < state.jump_until:
        progress = (state.jump_until - now) / 0.4
        jump_offset = int(math.sin(progress * math.pi) * 3)
    
    output_lines = []
    
    # Top border
    output_lines.append(f"{fg(BORDER_COLOR)}{'─' * width}{RESET}")
    
    for row in range(HERO_HEIGHT):
        line_parts = []
        
        # Check if we should render sprite on this row
        sprite_row = row - cat_y + jump_offset
        if 0 <= sprite_row < len(sprite_lines):
            # Calculate left padding to position the cat
            sprite_line = sprite_lines[sprite_row]
            # Use visual width for positioning
            effective_cat_x = max(0, min(cat_x, width - sw))
            left_pad = effective_cat_x
            right_pad = max(0, width - left_pad - sw)
            
            line_parts.append(" " * left_pad)
            line_parts.append(sprite_line)
            if right_pad > 0:
                line_parts.append(" " * right_pad)
        else:
            # Empty row
            line_parts.append(" " * width)
        
        output_lines.append("".join(line_parts))
    
    # Bottom border
    output_lines.append(f"{fg(BORDER_COLOR)}{'─' * width}{RESET}")
    
    return output_lines

# ═══════════════════════════════════════════════════════════════════════════════
# REST OF RENDERING 
# ═══════════════════════════════════════════════════════════════════════════════

def render_status_line(state: AppState, width: int) -> str:
    total_agents = len(MOCK_AGENTS)
    hot_agents   = sum(1 for a in MOCK_AGENTS if a["status"] == "HOT")
    alert_count  = len(MOCK_ALERTS)
    total_tok = state.latest_tokens if state.latest_tokens > 0 else sum(a["tok"] for a in MOCK_AGENTS)

    parts = [
        f"{fg(PINK)}{bold()}Mochi{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}{state.mode}{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(GREEN)}{bold()}{total_agents} agents{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(HOT)}{bold()}{hot_agents} hot{RESET}" if hot_agents else f"{fg(TEXT_DIM)}0 hot{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(HOT)}{alert_count} alert{RESET}" if alert_count else f"{fg(TEXT_DIM)}0 alerts{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}{total_tok} tokens{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}{state.model_name}{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(MINT)}L{state.eco_level}:{state.flower_stage}{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}save {state.prompt_tokens_saved_recent} tok{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}co2 {state.latest_co2_kg:.4f}kg{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(GREEN)}d: dashboard{RESET}",
    ]
    return f"{bg(BG_SURFACE2)}{' '.join(parts)}{RESET}"


def render_life_bar(state: AppState, cells: int = 10) -> str:
    max_points = max(1, _safe_int(state.life_points_max, 100))
    life = max(0, min(max_points, _safe_int(state.life_points, 0)))
    ratio = life / max_points
    filled = int(round(ratio * max(1, cells)))
    filled = max(0, min(cells, filled))
    empty = max(0, cells - filled)
    color = GREEN if ratio >= 0.6 else (YELLOW if ratio >= 0.3 else HOT)
    bar = f"[{('#' * filled)}{('-' * empty)}]"
    return f"{fg(color)}life {life:>3}/{max_points} {bar}{RESET}"


def render_life_line(state: AppState, width: int) -> str:
    life_bar = render_life_bar(state, cells=16)
    text = f" {life_bar} "
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    if len(plain) > width:
        life_bar = render_life_bar(state, cells=10)
        text = f" {life_bar} "
        plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    pad = max(0, width - len(plain))
    return f"{bg(BG_SURFACE)}{text}{' ' * pad}{RESET}"


def render_welcome(width: int) -> list[str]:
    lines_text = [
        ("Hi, I'm Mochi.", PINK, True),
        ("I explain edge-agent behavior and optimization.", TEXT_DIM, False),
        ("Type /agents, /inspect camera-agent, or ask me anything.", TEXT_DIM, False),
        (f"Dashboard running at {DASHBOARD_URL}", GREEN, False),
        ("Tip: /level shows carbon-linked flower progression.", TEXT_DIM, False),
    ]
    out = [""]
    for text, color, is_bold in lines_text:
        pad = (width - len(text)) // 2
        b = bold() if is_bold else ""
        out.append(f"{' ' * pad}{fg(color)}{b}{text}{RESET}")
    out.append("")
    return out


def render_divider(width: int) -> str:
    dots    = "·" * min(width - 4, 60)
    padding = (width - len(dots)) // 2
    return f"{' ' * padding}{fg(BORDER_COLOR)}{dots}{RESET}"


def expand_transcript_entries(state: AppState, width: int) -> list[str]:
    all_lines = []
    for entry in state.transcript:
        entry_type, prefix, text, card_data = entry
        prefix_str = prefix.ljust(8)
        if entry_type == "user":
            all_lines.append(f"  {fg(GREEN)}{bold()}{prefix_str}{RESET}{fg(TEXT_MAIN)}{text}{RESET}")
        elif entry_type == "mochi":
            all_lines.append(f"  {fg(PINK)}{bold()}{prefix_str}{RESET}{fg(TEXT_MAIN)}{text}{RESET}")
        elif entry_type == "system":
            all_lines.append(f"  {fg(TEXT_DIMMER)}{prefix_str}{text}{RESET}")
        elif entry_type == "warning":
            all_lines.append(f"  {fg(HOT)}{bold()}{prefix_str}{RESET}{fg(HOT)}{text}{RESET}")
        elif entry_type == "ok":
            all_lines.append(f"  {fg(GREEN)}{bold()}{prefix_str}{RESET}{fg(MINT)}{text}{RESET}")
        if card_data:
            all_lines.extend(render_card(card_data, width - 4))
    return all_lines


def render_transcript(state: AppState, width: int, max_lines: int) -> list[str]:
    all_lines = expand_transcript_entries(state, width)
    total     = len(all_lines)
    scroll    = state.transcript_scroll
    if total <= max_lines - 1:
        visible = all_lines
    else:
        end   = total - scroll
        start = max(0, end - (max_lines - 1))
        end   = min(total, start + max_lines - 1)
        visible = all_lines[start:end]
    lines = visible.copy()
    if scroll > 0:
        lines.append(f"  {fg(TEXT_DIMMER)}↓ {scroll} more lines below (press ↓ or End){RESET}")
    elif total > max_lines - 1:
        lines.append(f"  {fg(TEXT_DIMMER)}─ {total} lines total ─{RESET}")
    while len(lines) < max_lines:
        lines.append("")
    return lines[:max_lines]


def render_card(card_data: dict, width: int) -> list[str]:
    lines = []
    card_type = card_data.get("type", "")
    if card_type == "roster":
        lines.append("")
        header = f"{'NAME':<16} {'STATUS':<8} {'CPU':>5} {'MEM':>6} {'TOK/MIN':>8} {'LATENCY':>8} {'OPTIMIZER':<12}"
        lines.append(f"  {fg(TEXT_DIM)}{header}{RESET}")
        lines.append(f"  {fg(BORDER_COLOR)}{'─' * len(header)}{RESET}")
        for agent in card_data.get("agents", []):
            sc   = HOT if agent["status"] == "HOT" else GREEN
            name = agent["name"][:16].ljust(16)
            st   = agent["status"].ljust(8)
            cpu  = f"{agent['cpu']}%".rjust(5)
            mem  = f"{agent['mem']}M".rjust(6)
            tok  = str(agent["tok"]).rjust(8)
            lat  = f"{agent.get('latency',0)}ms".rjust(8)
            opt  = agent.get("optimizer","none")[:12].ljust(12)
            lines.append(f"  {fg(TEXT_MAIN)}{name}{RESET} {fg(sc)}{st}{RESET} {fg(TEXT_DIM)}{cpu} {mem} {tok} {lat}{RESET} {fg(TEXT_DIM)}{opt}{RESET}")
        lines.append("")
    elif card_type == "detail":
        agent = card_data.get("agent", {})
        sc    = HOT if agent.get("status") == "HOT" else GREEN
        lines += [
            "",
            f"  {fg(PINK)}{bold()}Agent: {agent.get('name','Unknown')}{RESET}",
            f"  {fg(TEXT_DIM)}Status:{RESET}     {fg(sc)}{agent.get('status','OK')}{RESET}",
            f"  {fg(TEXT_DIM)}CPU:{RESET}        {fg(TEXT_MAIN)}{agent.get('cpu',0)}%{RESET}",
            f"  {fg(TEXT_DIM)}Memory:{RESET}     {fg(TEXT_MAIN)}{agent.get('mem',0)}MB{RESET}",
            f"  {fg(TEXT_DIM)}Temp:{RESET}       {fg(TEXT_MAIN)}{agent.get('temp',0)}C{RESET}",
            f"  {fg(TEXT_DIM)}Tokens/min:{RESET} {fg(TEXT_MAIN)}{agent.get('tok',0)}{RESET}",
            f"  {fg(TEXT_DIM)}Latency:{RESET}    {fg(TEXT_MAIN)}{agent.get('latency',0)}ms{RESET}",
            f"  {fg(TEXT_DIM)}Optimizer:{RESET}  {fg(TEXT_MAIN)}{agent.get('optimizer','none')}{RESET}",
            "",
        ]
    elif card_type == "summary":
        total       = len(MOCK_AGENTS)
        hot         = sum(1 for a in MOCK_AGENTS if a["status"] == "HOT")
        alerts      = len(MOCK_ALERTS)
        total_tok   = sum(a["tok"] for a in MOCK_AGENTS)
        avg_cpu     = sum(a["cpu"] for a in MOCK_AGENTS) // total
        most_active = max(MOCK_AGENTS, key=lambda a: a["tok"])
        lines += [
            "",
            f"  {fg(PINK)}{bold()}System Summary{RESET}",
            f"  {fg(TEXT_DIM)}Agents:{RESET}       {fg(GREEN)}{total}{RESET}",
            f"  {fg(TEXT_DIM)}Hot:{RESET}          {fg(HOT if hot else TEXT_DIM)}{hot}{RESET}",
            f"  {fg(TEXT_DIM)}Alerts:{RESET}       {fg(HOT if alerts else TEXT_DIM)}{alerts}{RESET}",
            f"  {fg(TEXT_DIM)}Total tok/min:{RESET} {fg(TEXT_MAIN)}{total_tok}{RESET}",
            f"  {fg(TEXT_DIM)}Avg CPU:{RESET}      {fg(TEXT_MAIN)}{avg_cpu}%{RESET}",
            f"  {fg(TEXT_DIM)}Most active:{RESET}  {fg(PINK)}{most_active['name']}{RESET}",
            f"  {fg(TEXT_DIM)}Last action:{RESET}  {fg(MINT)}prompt compression{RESET}",
            "",
        ]
    elif card_type == "alerts":
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}Active Alerts{RESET}")
        for i, alert in enumerate(MOCK_ALERTS, 1):
            lines.append(f"  {fg(HOT)}{i}. {alert}{RESET}")
        lines.append("")
    elif card_type == "compare":
        agent = card_data.get("agent", {})
        lines += [
            "",
            f"  {fg(PINK)}{bold()}{agent.get('name','Unknown')} Optimization Compare{RESET}",
            f"  {fg(TEXT_DIM)}Before:{RESET} CPU 92% | Tokens 2450/min | Latency 610ms",
            f"  {fg(GREEN)}After:{RESET}  CPU {agent.get('cpu',85)}% | Tokens {agent.get('tok',1997)}/min | Latency {agent.get('latency',540)}ms",
            f"  {fg(MINT)}Savings: 7% CPU | 18% tokens | 11% latency{RESET}",
            "",
        ]
    elif card_type == "dashboard":
        lines += [
            "",
            f"  {fg(PINK)}{bold()}Dashboard{RESET}",
            f"  {fg(TEXT_DIM)}URL:{RESET} {fg(GREEN)}{DASHBOARD_URL}{RESET}",
            f"  {fg(TEXT_DIM)}Open in browser for charts and trends.{RESET}",
            "",
        ]
    elif card_type == "carbon_plan":
        devices = card_data.get("devices", [])
        threshold = _safe_float(card_data.get("threshold"), 0.0)
        current_ci = _safe_float(card_data.get("current_ci"), 0.0)
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}CarbonMin Device Ranking{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}CurrentCI={current_ci:.4f}kg | Threshold={threshold:.4f}kg{RESET}")
        header = f"{'DEVICE':<16} {'CI(kg)':>10} {'TOKENS':>10} {'CPU%':>7} {'EFF':>12}"
        lines.append(f"  {fg(TEXT_DIM)}{header}{RESET}")
        lines.append(f"  {fg(BORDER_COLOR)}{'─' * len(header)}{RESET}")
        for item in devices:
            dev = str(item.get("ip", "unknown"))[:16].ljust(16)
            ci = f"{_safe_float(item.get('ci')):.4f}".rjust(10)
            tok = str(_safe_int(item.get("tokens"))).rjust(10)
            cpu = f"{_safe_float(item.get('cpu')):.1f}".rjust(7)
            eff = f"{_safe_float(item.get('perf_per_carbon')):.1f}".rjust(12)
            lines.append(f"  {fg(TEXT_MAIN)}{dev}{RESET} {fg(TEXT_DIM)}{ci} {tok} {cpu} {eff}{RESET}")
        lines.append("")
    return lines


def render_prompt(state: AppState, width: int) -> str:
    prompt = f"  {fg(GREEN)}{bold()}>{RESET} "
    if state.input_buffer:
        return f"{prompt}{fg(TEXT_MAIN)}{state.input_buffer}{RESET}"
    return f"{prompt}{fg(TEXT_DIMMER)}Ask Mochi or type /help{RESET}"


def render_hints(width: int) -> str:
    hints = [
        (f"{fg(GREEN)}{bold()}Enter{RESET}", f"{fg(TEXT_DIMMER)}send{RESET}"),
        (f"{fg(GREEN)}↑↓{RESET}",           f"{fg(TEXT_DIMMER)}scroll{RESET}"),
        (f"{fg(PINK)}W{RESET}",             f"{fg(TEXT_DIMMER)}walk{RESET}"),
        (f"{fg(PINK)}O{RESET}",             f"{fg(TEXT_DIMMER)}opt+sync{RESET}"),
        (f"{fg(PINK)}P{RESET}",             f"{fg(TEXT_DIMMER)}plan{RESET}"),
        (f"{fg(PINK)}F{RESET}",             f"{fg(TEXT_DIMMER)}feed{RESET}"),
        (f"{fg(PINK)}N{RESET}",             f"{fg(TEXT_DIMMER)}nap{RESET}"),
        (f"{fg(GREEN)}/agents{RESET}",      f"{fg(TEXT_DIMMER)}list{RESET}"),
        (f"{fg(GREEN)}/dashboard{RESET}",   f"{fg(TEXT_DIMMER)}open{RESET}"),
        (f"{fg(GREEN)}q{RESET}",            f"{fg(TEXT_DIMMER)}quit{RESET}"),
    ]
    parts = ["  "]
    for key, desc in hints:
        parts.append(f"{key} {desc}  ")
    return f"{bg(BG_SURFACE2)}{''.join(parts)}{RESET}"


def render_screen(state: AppState) -> str:
    rows, cols = get_terminal_size()
    output = []

    output.append(render_status_line(state, cols))
    output.append(render_popup_line(state, cols))
    output.append(render_life_line(state, cols))
    output.extend(render_hero_nyan(state, cols, rows))
    output.extend(render_welcome(cols))
    output.append(render_divider(cols))
    output.append("")

    used_rows     = len(output) + 3
    transcript_rows = max(4, rows - used_rows)
    output.extend(render_transcript(state, cols, transcript_rows))
    output.append(render_prompt(state, cols))
    output.append(render_hints(cols))

    while len(output) < rows:
        output.append("")
    output = output[:rows]

    padded = [clear_line() + line for line in output]
    return "\033[H" + hide_cursor() + "\n".join(padded)


def render_popup_line(state: AppState, width: int) -> str:
    if time.time() > state.popup_until or not state.popup_title:
        return f"{bg(BG_SURFACE)}{' ' * width}{RESET}"

    kind_color = {
        "ok": GREEN,
        "warn": HOT,
        "info": MINT,
    }.get(state.popup_kind, MINT)
    msg = f" {state.popup_title}: {state.popup_detail} "
    if len(msg) > width:
        msg = msg[: max(0, width - 3)] + "..."
    pad = max(0, width - len(msg))
    return f"{bg(BG_SURFACE)}{fg(kind_color)}{bold()}{msg}{RESET}{bg(BG_SURFACE)}{' ' * pad}{RESET}"


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMATION TRIGGERS - W, P, N keys
# ═══════════════════════════════════════════════════════════════════════════════

def trigger_walk(state: AppState) -> None:
    """W key - Trigger walking animation."""
    state.mood = "happy"
    state.mood_timer = 180  # Walk takes a bit less time
    state.walk_until = time.time() + 3.0  # 3 seconds walk (reduced from 4)
    state.walk_offset = 0
    state.walk_direction = 1

def trigger_party(state: AppState) -> None:
    """P key - Trigger party mood with jump."""
    state.mood = "celebrate"
    state.mood_timer = 90
    state.jump_until = time.time() + 0.4

def trigger_nap(state: AppState) -> None:
    """N key - Trigger sleep mode."""
    state.mood = "sleeping"
    state.mood_timer = 200


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_ipv4(candidate: str) -> Optional[str]:
    """Validate and normalize an IPv4 address string."""
    value = candidate.strip()
    value = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    value = value.split("/", 1)[0]

    # Accept host:port format and keep host part.
    if ":" in value:
        host, port = value.rsplit(":", 1)
        if port and not port.isdigit():
            return None
        value = host

    if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", value):
        return None

    octets = value.split(".")
    for octet in octets:
        n = int(octet)
        if n < 0 or n > 255:
            return None
    return ".".join(str(int(o)) for o in octets)


def parse_ip_list(raw: str) -> tuple[list[str], list[str]]:
    """Parse one or more IPs from a comma/space separated string."""
    tokens = [t for t in re.split(r"[\s,]+", raw.strip()) if t]
    valid: list[str] = []
    invalid: list[str] = []
    seen = set()

    for token in tokens:
        normalized = normalize_ipv4(token)
        if normalized:
            if normalized not in seen:
                valid.append(normalized)
                seen.add(normalized)
        else:
            invalid.append(token)

    return valid, invalid


def load_known_devices() -> list[str]:
    try:
        if not CONNECTED_DEVICES_FILE.exists():
            return []
        data = json.loads(CONNECTED_DEVICES_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []

        cleaned = []
        seen = set()
        for item in data:
            if not isinstance(item, str):
                continue
            ip = normalize_ipv4(item)
            if ip and ip not in seen:
                cleaned.append(ip)
                seen.add(ip)
        return cleaned
    except Exception:
        return []


def save_known_devices(devices: list[str]) -> None:
    try:
        CONNECTED_DEVICES_FILE.write_text(json.dumps(devices, indent=2), encoding="utf-8")
    except Exception:
        pass


def fetch_device_status(ip: str) -> tuple[Optional[dict], Optional[str]]:
    url = f"http://{ip}:{DEVICE_STATUS_PORT}/status"
    try:
        with urllib.request.urlopen(url, timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return None, "invalid JSON payload"
            return payload, None
    except urllib.error.URLError as exc:
        return None, str(exc.reason)
    except TimeoutError:
        return None, "request timed out"
    except Exception as exc:
        return None, str(exc)


def set_popup(state: AppState, title: str, detail: str, kind: str = "info", ttl_s: float = 3.0) -> None:
    state.popup_title = title
    state.popup_detail = detail
    state.popup_kind = kind
    state.popup_until = time.time() + max(0.5, ttl_s)


def award_life_points(state: AppState, amount: int, reason: str) -> int:
    if amount == 0:
        return 0
    max_points = max(1, _safe_int(state.life_points_max, 100))
    before = max(0, min(max_points, _safe_int(state.life_points, 0)))
    after = max(0, min(max_points, before + amount))
    delta = after - before
    state.life_points = after
    if delta != 0:
        state.transcript.append((
            "system",
            "life",
            f"Life {'+' if delta > 0 else ''}{delta} ({reason}) -> {after}/{max_points}",
            None,
        ))
    return delta


def calculate_percentile(values: list[float], percentile: float) -> float:
    data = sorted(v for v in values if v >= 0)
    if not data:
        return 0.0
    if len(data) == 1:
        return data[0]
    p = max(0.0, min(100.0, percentile)) / 100.0
    idx = p * (len(data) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return data[lo]
    frac = idx - lo
    return data[lo] * (1.0 - frac) + data[hi] * frac


def _device_carbon_intensity(payload: dict) -> float:
    kg = _safe_float(payload.get("kg_co2e"), 0.0)
    if kg > 0:
        return kg
    energy_wh = _safe_float(payload.get("energy_wh"), 0.0)
    if energy_wh > 0:
        return (energy_wh / 1000.0) * GRID_KG_CO2E_PER_KWH
    return 0.0


def build_device_efficiency_rankings(state: AppState) -> list[dict]:
    rankings: list[dict] = []
    for ip in state.known_devices:
        payload, err = fetch_device_status(ip)
        if err or not payload:
            continue
        ci = _device_carbon_intensity(payload)
        tok = _safe_int(payload.get("total_tokens"), 0)
        cpu = _safe_float(payload.get("cpu_usage"), 0.0)
        perf = (tok + 1) / max(ci, 0.000001)
        rankings.append({
            "ip": ip,
            "ci": ci,
            "tokens": tok,
            "cpu": cpu,
            "perf_per_carbon": perf,
        })

    rankings.sort(key=lambda r: (r.get("ci", 0.0), -r.get("perf_per_carbon", 0.0), r.get("cpu", 0.0)))
    state.last_device_rankings = rankings
    return rankings


def _estimate_feed_tokens(state: AppState) -> int:
    if state.prompt_tokens_saved_recent > 0:
        return max(50, min(1200, state.prompt_tokens_saved_recent))
    if state.latest_tokens > 0:
        return max(50, min(1200, int(state.latest_tokens * 0.08)))
    return 200


def _enqueue_carbon_task(state: AppState, tokens: int) -> CarbonTask:
    task: CarbonTask = {
        "id": f"task-{int(time.time() * 1000)}",
        "arrival_time": time.time(),
        "tokens": max(1, tokens),
        "status": "queued",
        "assigned_ip": "",
        "decision": "defer",
    }
    state.carbon_task_queue.append(task)
    return task


def run_carbonmin_scheduler(state: AppState) -> dict:
    rankings = build_device_efficiency_rankings(state)
    cis = [float(item.get("ci", 0.0)) for item in rankings if _safe_float(item.get("ci"), 0.0) > 0]
    if state.latest_co2_kg > 0:
        cis.append(state.latest_co2_kg)
    threshold = calculate_percentile(cis, state.carbon_threshold_percentile)
    current_ci = cis[0] if cis else state.latest_co2_kg

    dispatched = 0
    deferred = 0
    best = rankings[0] if rankings else None

    for task in list(state.carbon_task_queue):
        if str(task.get("status")) != "queued":
            continue
        age_s = max(0.0, time.time() - _safe_float(task.get("arrival_time"), time.time()))
        should_dispatch = (current_ci <= threshold) or (age_s >= state.carbon_max_delay_s)
        if should_dispatch and best:
            task["status"] = "dispatched"
            task["assigned_ip"] = str(best.get("ip", ""))
            task["decision"] = "dispatch"
            task["dispatch_time"] = time.time()
            task["threshold"] = threshold
            task["current_ci"] = current_ci
            state.carbon_allocation_history.append(dict(task))
            state.carbon_task_queue.remove(task)
            dispatched += 1
        else:
            task["decision"] = "defer"
            task["threshold"] = threshold
            task["current_ci"] = current_ci
            deferred += 1

    return {
        "threshold": threshold,
        "current_ci": current_ci,
        "dispatched": dispatched,
        "deferred": deferred,
        "best": best,
        "rankings": rankings,
    }


def trigger_carbon_plan(state: AppState) -> None:
    result = run_carbonmin_scheduler(state)
    rankings = result.get("rankings", [])
    if not rankings:
        state.transcript.append(("warning", "carbon", "No reachable devices for CarbonMin planning.", None))
        set_popup(state, "CarbonMin", "No reachable devices", kind="warn", ttl_s=3.0)
        state.mood = "sad"
        state.mood_timer = 80
        return

    threshold = _safe_float(result.get("threshold"), 0.0)
    current_ci = _safe_float(result.get("current_ci"), 0.0)
    top = rankings[0]
    state.transcript.append((
        "mochi",
        "Mochi",
        (
            f"CarbonMin plan: current_ci={current_ci:.4f}kg threshold(p{int(state.carbon_threshold_percentile)})={threshold:.4f}kg | "
            f"best={top.get('ip')}"
        ),
        {"type": "carbon_plan", "devices": rankings[:5], "threshold": threshold, "current_ci": current_ci},
    ))
    set_popup(state, "CarbonMin", f"Best device {top.get('ip')} at ci={_safe_float(top.get('ci')):.4f}", kind="info", ttl_s=3.0)
    state.mood = "thinking"
    state.mood_timer = 90


def trigger_feed_carbonmin(state: AppState) -> None:
    tokens = _estimate_feed_tokens(state)
    task = _enqueue_carbon_task(state, tokens)
    state.transcript.append(("system", "carbon", f"Queued {tokens} tokens for CarbonMin task {task['id']}", None))
    set_popup(state, "Feed", f"Queued {tokens} tokens for smart dispatch", kind="info", ttl_s=2.5)

    result = run_carbonmin_scheduler(state)
    dispatched = _safe_int(result.get("dispatched"), 0)
    deferred = _safe_int(result.get("deferred"), 0)
    threshold = _safe_float(result.get("threshold"), 0.0)
    current_ci = _safe_float(result.get("current_ci"), 0.0)
    best = result.get("best") if isinstance(result.get("best"), dict) else None

    if dispatched > 0 and best:
        ip = str(best.get("ip", "unknown"))
        state.transcript.append((
            "ok",
            "carbon",
            f"Dispatched {tokens} tokens to {ip} (ci={_safe_float(best.get('ci')):.4f} <= T={threshold:.4f}).",
            None,
        ))
        set_popup(state, "Feed Dispatch", f"{tokens} tokens -> {ip}", kind="ok", ttl_s=3.2)
        trigger_party(state)
    else:
        state.transcript.append((
            "warning",
            "carbon",
            f"Deferred task {task['id']} (ci={current_ci:.4f} > T={threshold:.4f}); queued until greener window/max delay.",
            None,
        ))
        set_popup(state, "Feed Deferred", f"Waiting greener window ({deferred} queued)", kind="warn", ttl_s=3.2)
        state.mood = "thinking"
        state.mood_timer = 80


def build_roster_from_status(ip: str, payload: dict) -> list[dict]:
    roster = []
    raw_agents = payload.get("agents", [])
    top_cpu = _safe_float(payload.get("cpu_usage", 0.0), 0.0)
    top_mem = _safe_float(payload.get("mem_usage", 0.0), 0.0)
    top_latency = _safe_float(payload.get("latency_ms", payload.get("latency", 0.0)), 0.0)
    top_temp = _safe_float(payload.get("temp", 0.0), 0.0)
    top_energy_wh = _safe_float(payload.get("energy_wh", 0.0), 0.0)
    top_kg_co2e = _safe_float(payload.get("kg_co2e", 0.0), 0.0)
    payload_total_tokens = _safe_int(payload.get("total_tokens", 0), 0)

    if not isinstance(raw_agents, list):
        raw_agents = []

    for item in raw_agents:
        if not isinstance(item, dict):
            continue
        cpu = _safe_float(item.get("cpu", top_cpu), top_cpu)
        mem_mb = _safe_float(item.get("memory_mb", top_mem), top_mem)
        latency_ms = _safe_float(item.get("latency_ms", item.get("latency", top_latency)), top_latency)
        # Treat HOT as actual compute pressure, not token-share metrics.
        status = "HOT" if cpu >= 80.0 or top_temp >= 70.0 else "OK"
        optimizer = str(item.get("importance", "none"))
        name = str(item.get("name", "agent"))
        tok = _safe_int(item.get("total_tokens", item.get("tok", payload_total_tokens)), 0)

        roster.append({
            "name": f"{name}@{ip}",
            "cpu": int(round(cpu)),
            "mem": int(round(mem_mb)),
            "tok": tok,
            "status": status,
            "latency": int(round(latency_ms)),
            "temp": _safe_float(payload.get("temp", 0.0), 0.0),
            "optimizer": optimizer,
        })

    # If the endpoint reports only top-level metrics, still render one useful row.
    if not roster:
        status = "HOT" if top_cpu >= 80.0 or top_temp >= 70.0 else "OK"
        roster.append({
            "name": f"device@{ip}",
            "cpu": int(round(top_cpu)),
            "mem": int(round(top_mem)),
            "tok": payload_total_tokens,
            "status": status,
            "latency": int(round(top_latency)),
            "temp": top_temp,
            "optimizer": f"energy={top_energy_wh:.6f}Wh co2={top_kg_co2e:.6g}kg",
        })

    return roster


def _tokens_from_node(node) -> int:
    if isinstance(node, dict):
        for prompt_key, completion_key, total_key in TOKEN_KEY_SETS:
            if total_key in node:
                return _safe_int(node.get(total_key), 0)
            if prompt_key in node and completion_key in node:
                return _safe_int(node.get(prompt_key), 0) + _safe_int(node.get(completion_key), 0)

        subtotal = 0
        for value in node.values():
            subtotal += _tokens_from_node(value)
        return subtotal

    if isinstance(node, list):
        subtotal = 0
        for item in node:
            subtotal += _tokens_from_node(item)
        return subtotal

    return 0


def _tail_jsonl_records(path: Path, max_lines: int = 250) -> list[dict]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception:
        return []

    records = []
    for line in lines[-max_lines:]:
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _latest_snapshot_record(path: Path) -> Optional[dict]:
    records = _tail_jsonl_records(path, max_lines=32)
    if not records:
        return None
    return records[-1]


def _snapshot_emission_kg(path: Path) -> tuple[float, int, str]:
    rec = _latest_snapshot_record(path)
    if not isinstance(rec, dict):
        return 0.0, 0, "none"
    totals = rec.get("totals") if isinstance(rec.get("totals"), dict) else {}
    energy = rec.get("energy") if isinstance(rec.get("energy"), dict) else {}
    total_tokens = _safe_int(totals.get("total_tokens"), 0)
    kwh = _safe_float(energy.get("kwh"), 0.0)
    if total_tokens <= 0:
        return 0.0, 0, "none"
    if kwh <= 0:
        kwh = (max(total_tokens, 0) / 500.0) * WH_PER_500_TOKENS / 1000.0
    return kwh * GRID_KG_CO2E_PER_KWH, total_tokens, "usage_snapshot"


def _estimate_kg_from_tokens(total_tokens: int) -> float:
    watt_hours = (max(total_tokens, 0) / 500.0) * WH_PER_500_TOKENS
    return (watt_hours / 1000.0) * GRID_KG_CO2E_PER_KWH


def _parse_iso_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _read_recent_jsonl(path: Path, max_lines: int = 400) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception:
        return []

    out = []
    for line in lines[-max_lines:]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def recent_prompt_efficiency(window_minutes: int = 60) -> dict:
    now = datetime.now(timezone.utc)
    records = _read_recent_jsonl(PROMPT_EFFICIENCY_LOG_FILE, max_lines=600)
    tokens_saved = 0
    carbon_saved_g = 0.0
    events = 0
    latest_ts = None

    for record in records:
        ts_raw = record.get("timestamp")
        if not isinstance(ts_raw, str):
            continue
        ts = _parse_iso_ts(ts_raw)
        if ts is None:
            continue
        if latest_ts is None or ts > latest_ts:
            latest_ts = ts

        age_s = (now - ts).total_seconds()
        if age_s > max(60, window_minutes * 60):
            continue

        events += 1
        tokens_saved += _safe_int(record.get("tokens_saved"), 0)
        carbon_saved_g += _safe_float(record.get("carbon_saved_g"), 0.0)

    return {
        "events": events,
        "tokens_saved": max(tokens_saved, 0),
        "carbon_saved_g": max(carbon_saved_g, 0.0),
        "latest_ts": latest_ts.isoformat() if latest_ts else None,
    }


def load_ingest_heartbeat() -> dict:
    if not INGEST_HEARTBEAT_FILE.exists():
        return {}
    try:
        data = json.loads(INGEST_HEARTBEAT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def file_age_seconds(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except Exception:
        return None


def compute_eco_level_and_flower(co2_kg: float, prompt_tokens_saved: int = 0) -> tuple[int, str]:
    """Lower CO2 raises base level; prompt savings can boost flower progression."""
    if co2_kg <= 0.01:
        base_level = 5
    elif co2_kg <= 0.03:
        base_level = 4
    elif co2_kg <= 0.08:
        base_level = 3
    elif co2_kg <= 0.20:
        base_level = 2
    else:
        base_level = 1

    bonus = 0
    if prompt_tokens_saved >= 250:
        bonus = 2
    elif prompt_tokens_saved >= 80:
        bonus = 1

    level = min(5, base_level + bonus)
    stage_by_level = {
        1: "seed",
        2: "sprout",
        3: "bud",
        4: "flower",
        5: "bloom",
    }
    return level, stage_by_level[level]


def update_environment_state(state: AppState, co2_kg: float, total_tokens: int, source: str) -> None:
    prompt_stats = recent_prompt_efficiency(window_minutes=60)
    tokens_saved = _safe_int(prompt_stats.get("tokens_saved"), 0)
    carbon_saved_g = _safe_float(prompt_stats.get("carbon_saved_g"), 0.0)
    state.latest_co2_kg = co2_kg
    state.latest_tokens = total_tokens
    state.latest_signal_source = source
    level, flower = compute_eco_level_and_flower(co2_kg, prompt_tokens_saved=tokens_saved)
    state.eco_level = level
    state.flower_stage = flower
    state.prompt_tokens_saved_recent = tokens_saved
    state.prompt_carbon_saved_recent_g = carbon_saved_g


def build_health_report(state: AppState) -> dict:
    prompt_age = file_age_seconds(PROMPT_EFFICIENCY_LOG_FILE)
    usage_age = file_age_seconds(USAGE_SNAPSHOT_FILE)

    reachable = 0
    for ip in state.known_devices:
        _, err = fetch_device_status(ip)
        if not err:
            reachable += 1

    heartbeat = load_ingest_heartbeat()
    hb_status = str(heartbeat.get("status", "missing")) if heartbeat else "missing"
    hb_age = None
    ts = heartbeat.get("timestamp") if isinstance(heartbeat, dict) else None
    if isinstance(ts, str):
        hb_dt = _parse_iso_ts(ts)
        if hb_dt is not None:
            hb_age = max(0.0, (datetime.now(timezone.utc) - hb_dt).total_seconds())

    validation = heartbeat.get("validation") if isinstance(heartbeat, dict) else None
    validated = 0
    if isinstance(validation, dict):
        validated = sum(1 for v in validation.values() if v)

    return {
        "prompt_log_exists": PROMPT_EFFICIENCY_LOG_FILE.exists(),
        "prompt_log_age_s": prompt_age,
        "usage_snapshot_exists": USAGE_SNAPSHOT_FILE.exists(),
        "usage_snapshot_age_s": usage_age,
        "emission_poll_inflight": state.emission_poll_inflight,
        "llm_inflight": state.llm_inflight,
        "optimize_workflow_inflight": state.optimization_workflow_inflight,
        "optimize_workflow_status": state.last_workflow_status,
        "optimize_workflow_error": state.last_workflow_error,
        "optimize_workflow_last_run_age_s": (
            max(0.0, time.time() - state.last_workflow_run_at)
            if state.last_workflow_run_at > 0
            else None
        ),
        "devices_configured": len(state.known_devices),
        "devices_reachable": reachable,
        "influx_heartbeat_status": hb_status,
        "influx_heartbeat_age_s": hb_age,
        "influx_points_written": _safe_int(heartbeat.get("points_written"), 0) if heartbeat else 0,
        "influx_valid_measurements": validated,
    }


def get_environment_signal(state: AppState) -> tuple[float, int, str]:
    """Prefer connected device status, fall back to local Copilot logs."""
    total_kg = 0.0
    total_tokens = 0
    reachable = 0
    for ip in state.known_devices:
        payload, err = fetch_device_status(ip)
        if err or not payload:
            continue
        reachable += 1
        total_kg += _safe_float(payload.get("kg_co2e", 0.0), 0.0)
        total_tokens += _safe_int(payload.get("total_tokens", 0), 0)

    if reachable > 0:
        return total_kg, total_tokens, "device_status"

    return get_latest_copilot_emission_kg()


def get_latest_copilot_emission_kg() -> tuple[float, int, str]:
    """Get latest CO2 estimate via dashboard token analyzer from VS Code user logs."""
    # Fast path: use local usage snapshot written by analyzer/watch pipeline.
    snap_kg, snap_tokens, snap_source = _snapshot_emission_kg(USAGE_SNAPSHOT_FILE)
    if snap_source != "none":
        return snap_kg, snap_tokens, snap_source

    try:
        from dashboard import agent_token_analyszer as token_analyzer

        workspace_storage_root = Path.home() / ".config" / "Code" / "User" / "workspaceStorage"
        analyzer_args = SimpleNamespace(
            session_file=[],
            sessions_dir=None,
            workspace_storage_root=workspace_storage_root,
        )
        session_files = token_analyzer.discover_session_files(analyzer_args)
        if not session_files:
            return 0.0, 0, "none"

        summary, _ = token_analyzer.summarize(session_files)
        totals = token_analyzer.aggregate_totals(summary)
        if totals.total_tokens <= 0:
            return 0.0, 0, "none"

        _, energy_kwh = token_analyzer.compute_energy(totals.total_tokens, WH_PER_500_TOKENS)
        co2_kg = energy_kwh * GRID_KG_CO2E_PER_KWH
        return co2_kg, totals.total_tokens, "token_analyzer"
    except Exception:
        # Fallback to direct session payload parsing from VS Code user logs.
        chat_glob = os.path.expanduser("~/.config/Code/User/workspaceStorage/*/chatSessions/*.jsonl")
        chat_files = [Path(p) for p in glob.glob(chat_glob)]
        chat_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for session_file in chat_files[:5]:
            session_records = _tail_jsonl_records(session_file, max_lines=400)
            for record in reversed(session_records):
                total_tokens = _tokens_from_node(record)
                if total_tokens > 0:
                    return _estimate_kg_from_tokens(total_tokens), total_tokens, "vscode_chat_sessions"

    return 0.0, 0, "none"


def trigger_optimize(state: AppState) -> None:
    """O key - optimize behavior and run ingest workflow together."""
    trigger_walk(state)
    co2_kg, total_tokens, source = get_environment_signal(state)
    update_environment_state(state, co2_kg, total_tokens, source)

    if source == "none":
        trigger_party(state)
        state.transcript.append((
            "warning",
            "optimize",
            "Optimize: no Copilot usage logs found, defaulting to WALK -> PARTY.",
            None,
        ))
        return

    if co2_kg >= CO2_THRESHOLD_KG:
        trigger_nap(state)
        state.transcript.append((
            "warning",
            "optimize",
            f"Optimize: WALK -> NAP (CO2={co2_kg:.4f}kg, tokens={total_tokens}, source={source}).",
            None,
        ))
    else:
        trigger_party(state)
        state.transcript.append((
            "ok",
            "optimize",
            f"Optimize: WALK -> PARTY (CO2={co2_kg:.4f}kg, tokens={total_tokens}, source={source}).",
            None,
        ))

    start_optimization_workflow(state, reason="hotkey_o")


def _latest_user_prompt(state: AppState) -> str:
    for entry in reversed(state.transcript):
        if len(entry) < 3:
            continue
        entry_type, _, text, _ = entry
        if entry_type != "user" or not isinstance(text, str):
            continue
        candidate = text.strip()
        if candidate and not candidate.startswith("/"):
            return candidate
    return ""


def _format_workflow_error(stage: str, result: subprocess.CompletedProcess) -> str:
    output = (result.stderr or result.stdout or "").strip().splitlines()
    detail = output[-1] if output else "no output"
    return f"{stage} failed (exit={result.returncode}): {detail}"


def start_optimization_workflow(state: AppState, reason: str = "manual") -> None:
    if state.optimization_workflow_inflight:
        state.transcript.append((
            "warning",
            "optimize",
            "Optimize workflow already running...",
            None,
        ))
        set_popup(state, "Optimize", "Workflow already running", kind="warn", ttl_s=2.5)
        return

    seed_prompt = _latest_user_prompt(state)
    state.optimization_workflow_inflight = True
    state.last_workflow_status = "running"
    state.last_workflow_error = ""
    state.transcript.append((
        "system",
        "workflow",
        "Optimize workflow started: prompt -> analyzer -> Influx ingest.",
        None,
    ))
    set_popup(state, "Optimize", "Prompt -> analyzer -> ingest running", kind="info", ttl_s=3.0)

    def _worker() -> None:
        notes: list[str] = []
        try:
            if seed_prompt:
                result = optimize_prompt(
                    seed_prompt,
                    last_system_prompt=state.last_system_prompt_sent,
                    source=f"tamagochi.{reason}",
                )
                if result.events:
                    saved = sum(event.tokens_saved for event in result.events)
                    notes.append(f"prompt optimized ({saved} tokens est. saved)")
                else:
                    notes.append("prompt optimizer found no rewrite")
            else:
                notes.append("no recent user prompt to optimize")

            analyzer_cmd = [
                sys.executable,
                str(ANALYZER_SCRIPT),
                "--log-dir",
                str(REPO_ROOT / "logs"),
                "--sources",
                "copilot,claude",
                "--skip-dedup",
            ]
            analyzer = subprocess.run(
                analyzer_cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=180,
            )
            if analyzer.returncode != 0:
                raise RuntimeError(_format_workflow_error("analyzer", analyzer))

            influx_token = os.getenv("INFLUX_TOKEN", "hackathon-dev-token").strip()
            influx_url = os.getenv("INFLUX_URL", "http://localhost:8086").strip()
            influx_org = os.getenv("INFLUX_ORG", "hackathon").strip()
            influx_bucket = os.getenv("INFLUX_BUCKET", "metrics").strip()
            ingest_cmd = [
                sys.executable,
                str(INFLUX_PUSH_SCRIPT),
                "--influx-url",
                influx_url,
                "--org",
                influx_org,
                "--bucket",
                influx_bucket,
                "--token",
                influx_token,
                "--validate-measurements",
            ]
            ingest = subprocess.run(
                ingest_cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=180,
            )
            if ingest.returncode != 0:
                raise RuntimeError(_format_workflow_error("influx ingest", ingest))

            summary_line = ""
            for line in reversed((ingest.stdout or "").splitlines()):
                if line.strip():
                    summary_line = line.strip()
                    break
            if summary_line:
                notes.append(summary_line)

            state.event_queue.put(("optimize_workflow", {"status": "ok", "notes": notes, "error": ""}))
        except Exception as exc:
            state.event_queue.put((
                "optimize_workflow",
                {"status": "error", "notes": notes, "error": str(exc)},
            ))

    threading.Thread(target=_worker, daemon=True).start()


def start_emission_poll(state: AppState) -> None:
    if state.emission_poll_inflight:
        return

    state.emission_poll_inflight = True

    def _worker() -> None:
        try:
            co2_kg, total_tokens, source = get_environment_signal(state)
            state.event_queue.put(("emission", (co2_kg, total_tokens, source)))
        except Exception as exc:
            state.event_queue.put(("emission_error", str(exc)))

    threading.Thread(target=_worker, daemon=True).start()


def start_llm_request(
    state: AppState,
    optimized_prompt: str,
    optimized_system_prompt: str,
    max_tokens: int | None,
    system_prompt: str,
) -> None:
    if state.llm_inflight:
        state.transcript.append(("warning", "alert", "LLM already processing a request...", None))
        return

    state.llm_inflight = True

    def _worker() -> None:
        try:
            response = call_ollama(
                state.model_name,
                optimized_prompt,
                optimized_system_prompt or None,
                max_tokens=max_tokens,
            )
            state.event_queue.put(("llm", {"response": response, "system_prompt": system_prompt}))
        except Exception as exc:
            state.event_queue.put(("llm", {"response": f"✦ Error: {exc}", "system_prompt": system_prompt}))

    threading.Thread(target=_worker, daemon=True).start()


def _apply_response_mood(state: AppState, response: str) -> None:
    lower = response.lower()
    if any(word in lower for word in ["great", "excellent", "perfect", "good", "nice", "optimized", "efficient"]):
        state.mood = "happy"
        state.mood_timer = 90
    elif any(word in lower for word in ["warning", "hot", "high", "issue", "problem", "concern"]):
        state.mood = "warning"
        state.mood_timer = 100
    elif any(word in lower for word in ["success", "improved", "reduced", "saved"]):
        state.mood = "celebrate"
        state.mood_timer = 90
    else:
        state.mood = "idle"
        state.mood_timer = 60


def process_background_events(state: AppState) -> None:
    while True:
        try:
            event, payload = state.event_queue.get_nowait()
        except queue.Empty:
            break

        if event == "emission":
            state.emission_poll_inflight = False
            co2_kg, total_tokens, source = payload
            update_environment_state(state, co2_kg, total_tokens, source)
        elif event == "emission_error":
            state.emission_poll_inflight = False
        elif event == "llm":
            state.llm_inflight = False
            response = str(payload.get("response", ""))
            state.last_system_prompt_sent = str(payload.get("system_prompt", ""))
            state.transcript.append(("mochi", "Mochii", response, None))
            _apply_response_mood(state, response)
        elif event == "optimize_workflow":
            state.optimization_workflow_inflight = False
            state.last_workflow_run_at = time.time()
            notes = payload.get("notes") if isinstance(payload, dict) else None
            if payload.get("status") == "ok":
                state.last_workflow_status = "ok"
                state.last_workflow_error = ""
                state.transcript.append((
                    "ok",
                    "workflow",
                    "Optimize workflow complete.",
                    None,
                ))
                if isinstance(notes, list):
                    for note in notes:
                        state.transcript.append(("system", "workflow", str(note), None))
                state.next_emission_refresh = 0.0
                bonus = 8 + min(12, max(0, state.prompt_tokens_saved_recent // 120))
                gained = award_life_points(state, bonus, reason="optimized workflow")
                set_popup(
                    state,
                    "Optimize",
                    f"Workflow complete, +{gained} life",
                    kind="ok",
                    ttl_s=3.0,
                )
                state.mood = "celebrate"
                state.mood_timer = 90
            else:
                state.last_workflow_status = "error"
                err = str(payload.get("error", "workflow failed")) if isinstance(payload, dict) else "workflow failed"
                state.last_workflow_error = err
                state.transcript.append(("warning", "workflow", f"Optimize workflow failed: {err}", None))
                award_life_points(state, -2, reason="optimize workflow failure")
                set_popup(state, "Optimize", "Workflow failed, -2 life", kind="warn", ttl_s=3.0)
                state.mood = "warning"
                state.mood_timer = 110


# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

def handle_command(state: AppState, cmd: str) -> None:
    cmd_lower = cmd.lower().strip()
    if cmd_lower == "/help":
        state.transcript.append(("mochi", "Mochi", "Here are the available commands:", None))
        for c in ["/connect <ip[,ip2...]>", "/devices", "/agents [ip[,ip2...]]", "/inspect <name>", "/alerts", "/summary",
                  "/compare <name>", "/dashboard", "/level", "/flower", "/health", "/replay", "/clear"]:
            state.transcript.append(("system", "·", c, None))
        state.transcript.append(("system", "·", "W=walk  O=optimize+sync  P=carbon-plan  F=feed-dispatch  N=nap  (hotkeys)", None))
        state.mood = "happy"; state.mood_timer = 90
    elif cmd_lower.startswith("/connect"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            state.transcript.append(("mochi", "Mochi", "Usage: /connect <ip[,ip2,...]>", None))
            state.mood = "thinking"
            state.mood_timer = 50
            return

        valid_ips, invalid_ips = parse_ip_list(parts[1])
        if invalid_ips:
            state.transcript.append((
                "warning",
                "alert",
                f"Invalid IP(s): {', '.join(invalid_ips)}",
                None,
            ))

        if not valid_ips:
            state.transcript.append(("warning", "alert", "No valid IPs to connect.", None))
            state.mood = "sad"
            state.mood_timer = 70
            return

        added = []
        for ip in valid_ips:
            if ip not in state.known_devices:
                state.known_devices.append(ip)
                added.append(ip)

        state.known_devices = sorted(state.known_devices, key=lambda ip: tuple(int(o) for o in ip.split(".")))
        save_known_devices(state.known_devices)

        if added:
            state.transcript.append((
                "ok",
                "ok",
                f"Connected device(s) added: {', '.join(added)}",
                None,
            ))
        else:
            state.transcript.append((
                "system",
                "info",
                "All provided devices were already connected.",
                None,
            ))

        state.transcript.append((
            "system",
            "devices",
            f"Known devices: {', '.join(state.known_devices)}",
            None,
        ))
        state.mood = "happy"
        state.mood_timer = 90
    elif cmd_lower == "/devices":
        if state.known_devices:
            state.transcript.append((
                "mochi",
                "Mochi",
                f"Connected devices: {', '.join(state.known_devices)}",
                None,
            ))
            state.mood = "happy"
        else:
            state.transcript.append((
                "warning",
                "alert",
                "No connected devices yet. Use /connect <ip> first.",
                None,
            ))
            state.mood = "sad"
        state.mood_timer = 80
    elif cmd_lower.startswith("/agents"):
        parts = cmd.split(maxsplit=1)
        target_devices = state.known_devices[:]

        if len(parts) > 1:
            valid_ips, invalid_ips = parse_ip_list(parts[1])
            if invalid_ips:
                state.transcript.append((
                    "warning",
                    "alert",
                    f"Invalid IP(s): {', '.join(invalid_ips)}",
                    None,
                ))

            if valid_ips:
                target_devices = valid_ips

                # Convenience: inline /agents IPs are remembered as known devices.
                changed = False
                for ip in valid_ips:
                    if ip not in state.known_devices:
                        state.known_devices.append(ip)
                        changed = True
                if changed:
                    state.known_devices = sorted(
                        state.known_devices,
                        key=lambda ip: tuple(int(o) for o in ip.split(".")),
                    )
                    save_known_devices(state.known_devices)

        if not target_devices:
            state.transcript.append((
                "warning",
                "alert",
                "No connected devices. Use /connect <ip> or /agents <ip>.",
                None,
            ))
            state.mood = "sad"
            state.mood_timer = 80
            return

        combined_agents = []
        reachable = 0
        for ip in target_devices:
            payload, err = fetch_device_status(ip)
            if err:
                state.transcript.append((
                    "warning",
                    "alert",
                    f"{ip}: failed to fetch /status ({err})",
                    None,
                ))
                continue

            reachable += 1

            cpu_usage = _safe_float(payload.get("cpu_usage", 0.0), 0.0)
            mem_usage = _safe_float(payload.get("mem_usage", 0.0), 0.0)
            temp = _safe_float(payload.get("temp", 0.0), 0.0)
            agent_count = len(payload.get("agents", [])) if isinstance(payload.get("agents", []), list) else 0
            state.transcript.append((
                "system",
                "status",
                f"{ip}: cpu={cpu_usage:.1f}% mem={mem_usage:.1f}% temp={temp:.1f}C agents={agent_count}",
                None,
            ))

            combined_agents.extend(build_roster_from_status(ip, payload))

        if combined_agents:
            state.transcript.append((
                "mochi",
                "Mochi",
                f"Live agents from {reachable}/{len(target_devices)} device(s):",
                {"type": "roster", "agents": combined_agents},
            ))
            state.mood = "thinking"
            state.mood_timer = 100
        else:
            state.transcript.append((
                "warning",
                "alert",
                "No agent data received from connected devices.",
                None,
            ))
            state.mood = "sad"
            state.mood_timer = 90
    elif cmd_lower.startswith("/inspect"):
        parts = cmd.split(maxsplit=1)
        if len(parts) > 1:
            name  = parts[1].lower()
            agent = next((a for a in MOCK_AGENTS if name in a["name"].lower()), None)
            if agent:
                state.transcript.append(("mochi", "Mochi", f"Details for {agent['name']}:",
                                          {"type": "detail", "agent": agent}))
                if agent["status"] == "HOT":
                    state.transcript.append(("mochi", "Mochi",
                                              "This one is the busiest agent right now!", None))
                state.mood = "thinking"
            else:
                state.transcript.append(("warning", "alert", f"Agent '{parts[1]}' not found", None))
                state.mood = "sad"
        else:
            state.transcript.append(("mochi", "Mochi", "Usage: /inspect <agent_name>", None))
        state.mood_timer = 60
    elif cmd_lower == "/alerts":
        state.transcript.append(("mochi", "Mochi", "Active alerts:", {"type": "alerts"}))
        state.transcript.append(("mochi", "Mochi", "Most pressure is coming from camera-agent.", None))
        state.mood = "warning"; state.mood_timer = 100
    elif cmd_lower == "/summary":
        state.transcript.append(("mochi", "Mochi", "Here's the latest system summary:",
                                  {"type": "summary"}))
        state.mood = "celebrate"; state.mood_timer = 90
    elif cmd_lower.startswith("/compare"):
        parts = cmd.split(maxsplit=1)
        if len(parts) > 1:
            name  = parts[1].lower()
            agent = next((a for a in MOCK_AGENTS if name in a["name"].lower()), None)
            if agent:
                state.transcript.append(("mochi", "Mochi", "Optimization comparison:",
                                          {"type": "compare", "agent": agent}))
                state.mood = "celebrate"
            else:
                state.transcript.append(("warning", "alert", f"Agent '{parts[1]}' not found", None))
                state.mood = "sad"
        else:
            state.transcript.append(("mochi", "Mochi", "Usage: /compare <agent_name>", None))
        state.mood_timer = 90
    elif cmd_lower == "/dashboard":
        import webbrowser, urllib.request
        state.transcript.append(("mochi", "Mochi", "Opening dashboard...", None))
        try:
            r = urllib.request.urlopen(DASHBOARD_URL, timeout=2)
            if r.code == 200:
                state.transcript.append(("ok", "ok", "Dashboard already running!", None))
                webbrowser.open(DASHBOARD_URL)
        except:
            state.transcript.append(("warning", "alert",
                                      "Dashboard not reachable. Try ./start_dashboard_bg.sh", None))
        state.transcript.append(("mochi", "Mochi", "Dashboard shows charts and trends!",
                                  {"type": "dashboard"}))
        state.mood = "happy"; state.mood_timer = 60
    elif cmd_lower == "/level":
        state.transcript.append((
            "mochi",
            "Mochi",
            (
                f"Level {state.eco_level} | flower={state.flower_stage} | "
                f"co2={state.latest_co2_kg:.4f}kg | tokens={state.latest_tokens} | source={state.latest_signal_source}"
            ),
            None,
        ))
        state.mood = "thinking"
        state.mood_timer = 70
    elif cmd_lower == "/flower":
        import webbrowser

        state.transcript.append(("mochi", "Mochi", "Opening flower level preview...", None))
        try:
            flower_page = Path(__file__).with_name("flower.html").resolve()
            webbrowser.open(flower_page.as_uri())
            state.transcript.append((
                "system",
                "flower",
                f"Flower stage={state.flower_stage} (level {state.eco_level}) | source={state.latest_signal_source}",
                None,
            ))
            state.mood = "happy"
        except Exception as exc:
            state.transcript.append(("warning", "alert", f"Could not open flower page: {exc}", None))
            state.mood = "sad"
        state.mood_timer = 70
    elif cmd_lower == "/health":
        report = build_health_report(state)
        state.transcript.append((
            "mochi",
            "Mochi",
            (
                "Pipeline health: "
                f"prompt_log={report['prompt_log_exists']} age={_safe_float(report['prompt_log_age_s']):.1f}s | "
                f"snapshot={report['usage_snapshot_exists']} age={_safe_float(report['usage_snapshot_age_s']):.1f}s | "
                f"workers emission={report['emission_poll_inflight']} llm={report['llm_inflight']} optimize={report['optimize_workflow_inflight']} | "
                f"devices {report['devices_reachable']}/{report['devices_configured']} reachable | "
                f"influx={report['influx_heartbeat_status']} age={_safe_float(report['influx_heartbeat_age_s']):.1f}s "
                f"points={report['influx_points_written']} validated={report['influx_valid_measurements']}"
            ),
            None,
        ))
        state.transcript.append((
            "system",
            "health",
            (
                f"Optimize workflow: status={report['optimize_workflow_status']} "
                f"last_run_age={_safe_float(report['optimize_workflow_last_run_age_s']):.1f}s "
                f"error={report['optimize_workflow_error'] or 'none'}"
            ),
            None,
        ))
        state.transcript.append((
            "system",
            "health",
            (
                f"Flower signal: stage={state.flower_stage} level={state.eco_level} | "
                f"co2={state.latest_co2_kg:.4f}kg + prompt_saved_60m={state.prompt_tokens_saved_recent} tok "
                f"({state.prompt_carbon_saved_recent_g:.4f}g)"
            ),
            None,
        ))
        state.mood = "thinking"
        state.mood_timer = 90
    elif cmd_lower == "/replay":
        state.transcript.append(("mochi", "Mochi", "Replaying last optimization event...", None))
        state.mood = "celebrate"; state.mood_timer = 120
    elif cmd_lower == "/clear":
        state.transcript.clear()
        state.transcript.append(("system", "[system]", "Transcript cleared.", None))
        state.mood = "idle"; state.mood_timer = 0
    else:
        state.transcript.append(("mochi", "Mochi", f"Unknown command: {cmd}. Try /help", None))
        state.mood = "thinking"; state.mood_timer = 60


def call_ollama(
    model: str,
    prompt: str,
    system_prompt: str = None,
    max_tokens: int | None = None,
) -> str:
    """Call Ollama API to get LLM response."""
    try:
        ollama_base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        url = f"{ollama_base_url}/api/generate"
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            data["system"] = system_prompt
        if max_tokens is not None:
            data["options"] = {"num_predict": int(max_tokens)}
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('response', '').strip()
    except urllib.error.URLError:
        return "✦ Ollama API is not reachable. Check OLLAMA_HOST or start Ollama on the host."
    except TimeoutError:
        return "✦ LLM is loading... please try again in a moment."
    except Exception as e:
        return f"✦ Error: {str(e)[:100]}"


def handle_natural_language(state: AppState, text: str) -> None:
    """Handle natural language input using Gemma3 LLM."""
    
    # System prompt for Mochii's personality - cute but precise
    system_prompt = """You are Mochii, a cute AI assistant for edge-agent monitoring.
Be direct and specific. Answer in 1-2 sentences max.
No fluff, no emojis. Just the facts, cutely stated.
Your name is Mochii (two i's).
Focus: agents, tokens, performance, optimization."""
    
    optimization = optimize_prompt(
        text,
        system_prompt=system_prompt,
        last_system_prompt=state.last_system_prompt_sent,
        source="tamagochi.app",
    )
    optimized_prompt = optimization.optimized_prompt.strip() or text.strip()
    if optimization.events:
        kinds = ", ".join(e.optimization_type for e in optimization.events)
        total_saved = sum(e.tokens_saved for e in optimization.events)
        state.transcript.append((
            "system",
            "[opt]",
            f"Prompt optimizer: {kinds} | est. tokens saved={total_saved} | max_tokens={optimization.max_tokens or 'default'}",
            None,
        ))

    # Add context
    agent_context = f"\n\nCurrent agents: {', '.join(a['name'] for a in MOCK_AGENTS)}"
    full_prompt = optimized_prompt + agent_context
    
    # Show thinking state
    state.mood = "thinking"
    state.mood_timer = 30
    
    state.transcript.append(("system", "[llm]", "Processing in background...", None))
    start_llm_request(
        state,
        optimized_prompt=full_prompt,
        optimized_system_prompt=optimization.optimized_system_prompt,
        max_tokens=optimization.max_tokens,
        system_prompt=system_prompt,
    )


def handle_input(state: AppState, text: str) -> None:
    state.transcript.append(("user", ">", text, None))
    if text.startswith("/"):
        handle_command(state, text)
    elif normalize_ipv4(text.strip()):
        handle_command(state, f"/connect {text.strip()}")
    else:
        handle_natural_language(state, text)


# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD INPUT
# ═══════════════════════════════════════════════════════════════════════════════

class KeyReader:
    def __enter__(self):
        if os.name == "nt":
            import msvcrt
            self._msvcrt = msvcrt
            return self
        import termios, tty, select
        self._select   = select
        self._termios  = termios
        self._stdin_fd = sys.stdin.fileno()
        self._old      = termios.tcgetattr(self._stdin_fd)
        tty.setcbreak(self._stdin_fd)
        return self

    def __exit__(self, *args):
        if os.name != "nt":
            self._termios.tcsetattr(self._stdin_fd, self._termios.TCSADRAIN, self._old)

    def read_key(self) -> Optional[str]:
        if os.name == "nt":
            if self._msvcrt.kbhit():
                key = self._msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    self._msvcrt.getwch()
                    return None
                return key
            return None
        ready, _, _ = self._select.select([sys.stdin], [], [], 0)
        if ready:
            return sys.stdin.read(1)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    state = AppState()
    state.known_devices = load_known_devices()

    import signal
    def handle_resize(signum, frame):
        pass
    if hasattr(signal, 'SIGWINCH'):
        signal.signal(signal.SIGWINCH, handle_resize)

    state.transcript.append(("system", "[system]", "Terminal session started.", None))
    state.transcript.append(("system", "[system]",
                              f"Dashboard: {DASHBOARD_URL} (use /dashboard to start)", None))
    if state.known_devices:
        state.transcript.append(("system", "[system]",
                                  f"Connected devices: {', '.join(state.known_devices)}", None))
    else:
        state.transcript.append(("system", "[system]",
                                  "No connected devices. Use /connect <ip> to add one.", None))

    tick_interval = 0.033   # ~30 fps
    last_render   = 0.0
    last_size     = (0, 0)

    sys.stdout.write(enter_alt_screen() + clear_screen())
    sys.stdout.flush()

    try:
        with KeyReader() as reader:
            while state.running:
                now          = time.time()
                current_size = get_terminal_size()
                if current_size != last_size:
                    last_render = 0
                    last_size   = current_size

                state.frame += 1

                # Random blink
                if random.random() < 0.015 and now > state.blink_until:
                    state.blink_until = now + 0.18

                # Mood timer countdown
                if state.mood_timer > 0:
                    state.mood_timer -= 1
                    if state.mood_timer == 0:
                        state.mood = "idle"

                process_background_events(state)

                if now >= state.next_emission_refresh:
                    start_emission_poll(state)
                    state.next_emission_refresh = now + EMISSION_REFRESH_INTERVAL_S

                # Auto-optimize when emissions cross threshold.
                if now >= state.next_auto_optimize_check and now >= state.auto_optimize_cooldown_until:
                    state.next_auto_optimize_check = now + AUTO_OPTIMIZE_INTERVAL_S
                    if state.latest_signal_source != "none" and state.latest_co2_kg >= CO2_THRESHOLD_KG:
                        trigger_optimize(state)
                        state.auto_optimize_cooldown_until = now + AUTO_OPTIMIZE_COOLDOWN_S
                        state.transcript.append((
                            "warning",
                            "optimize",
                            f"Auto optimize triggered: CO2={state.latest_co2_kg:.3f}kg (tokens={state.latest_tokens}) >= {CO2_THRESHOLD_KG:.3f}kg.",
                            None,
                        ))

                # ── Key handling ──────────────────────────────────────────────
                key = reader.read_key()
                if key:
                    # Global quit
                    if key == "\x03" or (key == "q" and not state.input_buffer):
                        state.running = False

                    # ── Animation hotkeys (only when input buffer is empty) ───────
                    elif key.lower() == "w" and not state.input_buffer:
                        trigger_walk(state)

                    elif key.lower() == "p" and not state.input_buffer:
                        trigger_carbon_plan(state)

                    elif key.lower() == "f" and not state.input_buffer:
                        trigger_feed_carbonmin(state)

                    elif key.lower() == "n" and not state.input_buffer:
                        trigger_nap(state)

                    elif key.lower() == "o" and not state.input_buffer:
                        trigger_optimize(state)

                    # ── Normal text input ────────────────────────────────────
                    elif key in ("\r", "\n"):
                        if state.input_buffer.strip():
                            handle_input(state, state.input_buffer.strip())
                            state.transcript_scroll = 0
                            state.input_buffer = ""

                    elif key in ("\x7f", "\b"):
                        state.input_buffer = state.input_buffer[:-1]

                    elif key == "\x1b":
                        time.sleep(0.01)
                        nk = reader.read_key()
                        if nk == "[":
                            ak = reader.read_key()
                            if ak == "A":   # up arrow — scroll up
                                r, c = get_terminal_size()
                                used  = 1 + 16 + 5 + 2 + 3
                                trows = max(4, r - used)
                                total = len(expand_transcript_entries(state, c))
                                mx    = max(0, total - trows + 1)
                                state.transcript_scroll = min(state.transcript_scroll + 3, mx)
                            elif ak == "B":  # down arrow — scroll down
                                state.transcript_scroll = max(0, state.transcript_scroll - 3)
                            elif ak == "F":  # End key
                                state.transcript_scroll = 0
                        else:
                            state.input_buffer = ""

                    elif key.isprintable():
                        state.input_buffer += key

                # ── Render ────────────────────────────────────────────────────
                if now - last_render > tick_interval:
                    sys.stdout.write(render_screen(state))
                    sys.stdout.flush()
                    last_render = now

                time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(exit_alt_screen() + show_cursor() + RESET)
        sys.stdout.flush()
        print("Mochi says goodbye! ✦")


if __name__ == "__main__":
    main()