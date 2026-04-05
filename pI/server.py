from fastapi import FastAPI
import psutil
import sys
import os
import time
from pathlib import Path
from dataclasses import asdict
from typing import Dict, Any, List

# Add the parent directory to the path so we can import from 'dashboard'
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dashboard.agent_token_analyszer import (
        summarize,
        discover_session_files,
        aggregate_totals,
        compute_energy
    )
    from dashboard.carbon_constants import PI_CARBON_PER_TOKEN_G
    from dashboard.green_prompt import summarize_batch_savings
except ImportError:
    # Fallback if imports fail
    def summarize(*args, **kwargs): return {}, {}
    def discover_session_files(*args, **kwargs): return []
    def aggregate_totals(*args, **kwargs): return None
    def compute_energy(t, f): return 0.0, 0.0
    PI_CARBON_PER_TOKEN_G = 0.00042
    def summarize_batch_savings(texts, tier): return {"carbon_saved_g": 0.0}

app = FastAPI(title="Mochi Metrics Server")

# Constants for Raspberry Pi 4 (approximate)
WATTAGE_IDLE = 3.0  # Watts
WATTAGE_MAX = 7.0   # Watts
WH_PER_500_TOKENS = 0.1 # Very rough estimate for Pi

class MockArgs:
    def __init__(self):
        self.sessions_dir = repo_root / "workspace_chat_logs"
        self.session_file = []
        # Fallback paths
        self.workspace_storage_root = Path.home() / ".config" / "Code" / "User" / "workspaceStorage"
        self.copilot_logs_dir = repo_root / "logs" / "copilot_raw"
        self.openclaw_logs = Path.home() / ".openclaw" / "logs"
        self.max_prompt_samples = 10 
        self.sources = "copilot,claude,openclaw"

@app.get("/logs")
def list_logs():
    """Helper to find where the logs actually are."""
    paths = [
        Path.home() / ".openclaw" / "logs",
        Path.home() / ".config" / "Code" / "User" / "workspaceStorage",
        repo_root / "workspace_chat_logs"
    ]
    
    found = {}
    for p in paths:
        if p.exists():
            try:
                files = list(p.glob("**/*.json*"))
                # Get 5 most recent
                files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                found[str(p)] = [
                    {"file": f.name, "size": f.stat().st_size, "modified": time.ctime(f.stat().st_mtime)}
                    for f in files[:5]
                ]
            except Exception as e:
                found[str(p)] = f"Error: {str(e)}"
    return found

@app.get("/metrics/bot")
def get_bot_info():
    """Specific endpoint for the running bot token info."""
    agent_data = get_agent_stats()
    total_tokens = agent_data.get("total_tokens", 0)
    limit = 1_000_000 # Matching the TUI's 1.0m limit
    percent = (total_tokens / limit) * 100 if limit > 0 else 0
    
    return {
        "bot_name": "openclaw-tui",
        "model": "google/gemini-3.1-flash-lite-preview",
        "tokens_used": total_tokens,
        "token_limit": limit,
        "usage_percent": round(percent, 2),
        "status_display": f"{total_tokens//1000}k/{limit//1000000}m ({int(percent)}%)"
    }

@app.get("/metrics")
async def get_all_metrics():
    return {
        "system": get_system_stats(),
        "agent": get_agent_stats(),
        "bot": get_bot_info(),
        "power": get_power_stats(),
        "timestamp": time.time()
    }

@app.get("/metrics/system")
def get_system_stats():
    cpu_load = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    # Get top python processes
    py_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            if 'python' in proc.info['name'].lower():
                py_processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "cpu_percent": proc.info['cpu_percent'],
                    "memory_mb": round(proc.info['memory_info'].rss / (1024 * 1024), 2)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    return {
        "cpu_load_percent": cpu_load,
        "memory_usage_percent": memory.percent,
        "memory_used_mb": round(memory.used / (1024 * 1024), 2),
        "memory_free_mb": round(memory.available / (1024 * 1024), 2),
        "cpu_count": psutil.cpu_count(),
        "uptime_seconds": round(time.time() - psutil.boot_time(), 2),
        "python_processes": sorted(py_processes, key=lambda x: x['cpu_percent'], reverse=True)[:5]
    }

@app.get("/metrics/agent")
def get_agent_stats():
    args = MockArgs()
    
    # Discovery from standard locations
    all_files = discover_session_files(args)
    
    # Recursive discovery for openclaw agents
    openclaw_root = Path.home() / ".openclaw" / "agents"
    if openclaw_root.exists():
        try:
            # Look for session files in any agent's sessions folder
            session_files = list(openclaw_root.glob("**/sessions/*.json*"))
            for f in session_files:
                if f not in all_files:
                    all_files.append(f)
        except Exception:
            pass

    summary = {}
    total_tokens = 0
    prompt_samples = []
    
    if all_files:
        summary_copilot, _ = summarize(
            all_files,
            prompt_samples,
            args.max_prompt_samples
        )
        totals = aggregate_totals(summary_copilot)
        if totals:
            total_tokens = totals.total_tokens
            summary = {agent: asdict(stats) for agent, stats in summary_copilot.items()}

    # Green prompt savings
    savings = summarize_batch_savings(prompt_samples, tier="pi")

    return {
        "total_tokens": total_tokens,
        "active_agents": list(summary.keys()),
        "per_agent_stats": summary,
        "efficiency": savings,
        "log_sources": [str(f) for f in all_files]
    }

@app.get("/metrics/power")
def get_power_stats():
    cpu_load = psutil.cpu_percent(interval=None) # Use None to avoid blocking
    wattage = WATTAGE_IDLE + (WATTAGE_MAX - WATTAGE_IDLE) * (cpu_load / 100.0)
    
    agent_stats = get_agent_stats()
    total_tokens = agent_stats["total_tokens"]
    
    # Energy from tokens
    energy_wh, energy_kwh = compute_energy(total_tokens, WH_PER_500_TOKENS)
    
    # Carbon footprint
    carbon_g = total_tokens * PI_CARBON_PER_TOKEN_G

    return {
        "estimated_instant_wattage": round(wattage, 2),
        "cumulative_token_energy_wh": round(energy_wh, 4),
        "estimated_carbon_g": round(carbon_g, 4),
        "unit": "Watts/Wh/g"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {
        "message": "Mochi Metrics Server is running.",
        "endpoints": ["/metrics", "/metrics/system", "/metrics/agent", "/metrics/power", "/health", "/logs"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
