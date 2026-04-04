# Raspberry Pi Edge Deployment

This document covers deploying Mochi on Raspberry Pi or other ARM-based edge devices.

## Requirements

- Raspberry Pi 4 (4GB+ RAM recommended)
- Python 3.10+
- Ollama for ARM64

## Installation on Pi

```bash
# Install Ollama for ARM
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a small model
ollama pull gemma3:270m  # Low RAM option

# Clone and set up
git clone https://github.com/joe-rabbit/hackathon
cd hackathon
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure for Pi
echo "MOCHI_MODEL=gemma3:270m" >> .env
echo "MOCHI_DEVICE_NAME=pi-01" >> .env
```

## Running on Pi

```bash
# Terminal UI
python -m tamagochi.app

# Dashboard (accessible from other devices)
streamlit run dashboard/app.py --server.address 0.0.0.0
```

## Performance Tips

- Use `gemma3:270m` for lower memory usage
- Set `MOCHI_POLL_INTERVAL=5.0` for less frequent updates
- Run dashboard separately from TUI to reduce load
