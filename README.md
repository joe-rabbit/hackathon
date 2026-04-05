# 🍡 Mochi - Edge AI Orchestrator UI

An interactive terminal companion and dashboard for monitoring and optimizing AI agents running on edge devices. Mochi explains what the orchestrator does in plain English while providing real-time visibility into agent performance.

**The backend decides; Mochi explains.**

![Mochi TUI](https://via.placeholder.com/800x400?text=Mochi+Terminal+UI)

## ✨ Features

- **🖥️ Interactive Terminal UI** - Claude Code-style interface with multi-pane layout
- **🍡 Animated Mochi Companion** - Reacts to system state with moods and animations
- **📊 Live Agent Monitoring** - Real-time CPU, memory, tokens, and latency metrics
- **⚡ Optimization Tracking** - Before/after comparisons for optimizer actions
- **💬 Hybrid Commands** - Slash commands for actions + natural language for explanations
- **🤖 Local LLM Integration** - Grounded explanations via Ollama (no cloud required)
- **📈 Web Dashboard** - Streamlit-based visual analytics
- **🔌 Mock Mode** - Full functionality without a real backend

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) (for natural language features)

### Installation

```bash
# Clone the repository
git clone https://github.com/joe-rabbit/hackathon
cd hackathon

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
```

### Pull a Local LLM Model

```bash
# Install Ollama first, then:
ollama pull gemma3:1b     # Default model (fast)
# OR
ollama pull llama3.2:1b   # Alternative
# OR
ollama pull gemma3:270m   # Low RAM option
```

### Run the TUI

```bash
python -m tamagochi.app
```

### Run the Dashboard

```bash
streamlit run dashboard/app.py
```

## 🎮 Usage

### Terminal UI Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🍡 Mochi Edge AI Orchestrator │ 📍 edge-01 │ ◌ mock │ 🤖 gemma3:1b    │
├─────────────────────┬───────────────────────────┬───────────────────────┤
│ Agent Table         │ Chat Panel                │ Mochi + Details       │
│ ● nlp-agent    25%  │ > /agents                 │     ╭──────╮          │
│ 🔥 camera-agent 82% │ > why is camera hot?      │    ( O  O )          │
│ ◌ router-agent 12%  │ 🍡 Camera-agent is using  │     ╰──┬──╯          │
│                     │    high CPU because...    │    [CPU: 82%]        │
├─────────────────────┴───────────────────────────┴───────────────────────┤
│ Ctrl+Q Quit │ Ctrl+D Dashboard │ F1 Help │ Tab Navigate                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Slash Commands

| Command          | Description                 |
| ---------------- | --------------------------- |
| `/agents`        | List all agents with status |
| `/inspect <id>`  | Detailed view of an agent   |
| `/compare <id>`  | Before/after optimization   |
| `/alerts`        | Show active alerts          |
| `/summary`       | System overview             |
| `/optimize <id>` | Trigger optimization (demo) |
| `/dashboard`     | Open web dashboard          |
| `/replay`        | Replay last optimization    |
| `/help`          | Show all commands           |
| `/quit`          | Exit application            |

### Natural Language Questions

Ask Mochi anything about your agents:

- _"Why is camera-agent marked hot?"_
- _"What did the optimizer change for nlp-agent?"_
- _"Which agent is using the most tokens?"_
- _"Summarize the system status"_

### Keyboard Shortcuts

| Key      | Action                  |
| -------- | ----------------------- |
| `Ctrl+Q` | Quit                    |
| `Ctrl+D` | Open dashboard          |
| `F1`     | Show help               |
| `Tab`    | Cycle focus             |
| `↑/↓`    | Navigate agent table    |
| `Ctrl+O` | Optimize selected agent |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
├─────────────────────────────┬───────────────────────────────────┤
│     Terminal UI (Textual)   │     Dashboard (Streamlit)         │
├─────────────────────────────┴───────────────────────────────────┤
│                      Shared Services                             │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│  Backend │   Tool   │ Context  │   LLM    │   Mock Backend     │
│  Client  │  Router  │ Builder  │  Client  │                    │
├──────────┴──────────┴──────────┴──────────┴────────────────────┤
│                    Shared Schemas (Pydantic)                     │
├─────────────────────────────────────────────────────────────────┤
│                    Backend API / Mock Data                       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Backend computes, Mochi explains** - The optimizer makes decisions; the UI presents them
2. **Grounded responses only** - LLM never invents numbers; always based on fetched data
3. **Token-efficient context** - Context builder compresses data before sending to LLM
4. **Same schemas everywhere** - TUI and dashboard use identical Pydantic models

## 📁 Project Structure

```
hackathon/
├── shared/
│   ├── schemas.py      # Pydantic models for agents, alerts, etc.
│   └── config.py       # Environment-based configuration
├── tamagochi/
│   ├── app.py          # Main Textual application
│   ├── styles/app.tcss # TUI styles
│   ├── widgets/
│   │   ├── mochi_widget.py    # Animated Mochi sprite
│   │   ├── agent_table.py     # Live agent data table
│   │   ├── chat_panel.py      # Command/chat interface
│   │   └── ...
│   └── services/
│       ├── backend_client.py  # REST/WS backend adapter
│       ├── mock_backend.py    # Mock data generator
│       ├── tool_router.py     # Command routing
│       ├── context_builder.py # LLM context compression
│       └── llm_client.py      # Ollama integration
├── dashboard/
│   ├── app.py          # Streamlit main page
│   └── pages/
│       ├── 01_Overview.py
│       ├── 02_Agents.py
│       ├── 03_Optimizer_Impact.py
│       └── 04_Events.py
├── requirements.txt
├── .env.example
└── README.md
```

## ⚙️ Configuration

Edit `.env` to customize:

```bash
# Backend (leave empty for mock mode)
MOCHI_BACKEND_URL=http://127.0.0.1:8000
MOCHI_USE_MOCKS=1

# Local LLM
OLLAMA_HOST=http://127.0.0.1:11434
MOCHI_MODEL=gemma3:1b

# Dashboard
MOCHI_DASHBOARD_URL=http://127.0.0.1:8501

# Device name (shown in header)
MOCHI_DEVICE_NAME=edge-01
```

## 🎬 Demo Script

## 🔄 How to Replicate

If you want to spin this project up from scratch on a new machine, follow these exact steps:

1. **Set up the virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Or create one manually with MOCHI_USE_MOCKS=1
   ```

4. **Start the Local LLM (Ollama):**

   ```bash
   # Ensure ollama is installed on your OS
   ollama pull gemma3:1b
   ollama serve &
   ```

5. **Run the Interfaces (in separate terminals):**
   - **Terminal UI:** `python -m tamagochi.app`
   - **Web Dashboard:** `streamlit run dashboard/app.py`

6. **Start mock mode** with intentionally wasteful agents
7. **Open TUI**: `python -m tamagochi.app`
8. **See Mochi alive** in the terminal with blinking animation
9. **Run `/agents`** to see all agents
10. **Run `/inspect camera-agent`** to see the hot agent
11. **Ask**: _"Why is camera-agent wasting energy?"_
12. **Run `/optimize camera-agent`** to trigger optimization
13. **Watch Mochi celebrate** 🎉
14. **Run `/compare camera-agent`** to see before/after
15. **Press `Ctrl+D`** to open the dashboard

## 🔌 Backend API Contract

When connecting to a real backend, implement these endpoints:

| Endpoint        | Method | Description             |
| --------------- | ------ | ----------------------- |
| `/agents`       | GET    | List all agents         |
| `/agents/{id}`  | GET    | Get single agent        |
| `/summary`      | GET    | System summary          |
| `/alerts`       | GET    | Active alerts           |
| `/compare/{id}` | GET    | Optimization comparison |
| `/timeline`     | GET    | Event timeline          |
| `/ws/telemetry` | WS     | Real-time updates       |

See `shared/schemas.py` for detailed payload structures.

## 🧪 Development

```bash
# Run tests
pytest tests/

# Run TUI in development
python -m tamagochi.app

# Run dashboard with auto-reload
streamlit run dashboard/app.py --server.runOnSave true
```

## 🍡 Mochi's Moods

| Mood      | Trigger              | Animation    |
| --------- | -------------------- | ------------ |
| Idle      | Normal operation     | Gentle blink |
| Happy     | All systems OK       | Smiling      |
| Thinking  | LLM generating       | Bobbing      |
| Warning   | Agent hot/wasteful   | Worried face |
| Celebrate | Optimization success | Jump!        |
| Sleepy    | System calm          | Eyes closed  |

## 📝 License

MIT License - See LICENSE file

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Built with 💚 for the Hackathon | Powered by [Textual](https://textual.textualize.io/), [Streamlit](https://streamlit.io/), and [Ollama](https://ollama.ai/)
