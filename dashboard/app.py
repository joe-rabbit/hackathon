"""Mochi Dashboard - Streamlit web dashboard.

Provides visual analytics for the edge AI orchestrator using
the same shared schemas as the TUI.
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import settings
from shared.schemas import AgentStatus

# Page config
st.set_page_config(
    page_title="Mochi Dashboard",
    page_icon="🍡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #4CAF50;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .status-ok { color: #4CAF50; }
    .status-hot { color: #f44336; font-weight: bold; }
    .status-idle { color: #9e9e9e; }
</style>
""", unsafe_allow_html=True)


def get_mock_data():
    """Get mock data for the dashboard."""
    from tamagochi.services.mock_backend import get_mock_backend
    mock = get_mock_backend()

    # Tick a few times to generate some data
    for _ in range(3):
        mock.tick()

    return {
        "agents": mock.get_agents(),
        "summary": mock.get_summary(),
        "alerts": mock.get_alerts(),
        "timeline": mock.get_timeline(),
    }


def main():
    """Main dashboard page."""
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<p class="main-header">🍡 Mochi Dashboard</p>', unsafe_allow_html=True)
        st.caption("Edge AI Orchestrator - Real-time Monitoring")
    with col2:
        st.metric("Mode", "Mock" if settings().use_mocks else "Live")

    st.divider()

    # Load data
    data = get_mock_data()
    summary = data["summary"]
    agents = data["agents"]
    alerts = data["alerts"]

    # Summary metrics row
    st.subheader("System Overview")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Active Agents",
            summary.active_agents,
            delta=None,
        )

    with col2:
        delta_color = "inverse" if summary.hot_agents > 0 else "off"
        st.metric(
            "🔥 Hot Agents",
            summary.hot_agents,
            delta=f"{summary.hot_agents} need attention" if summary.hot_agents > 0 else None,
            delta_color=delta_color,
        )

    with col3:
        st.metric(
            "⚠️ Alerts",
            summary.alerts_open,
        )

    with col4:
        st.metric(
            "Tokens/min",
            f"{summary.tokens_per_min_total:,.0f}",
        )

    with col5:
        if summary.estimated_savings_pct:
            st.metric(
                "Est. Savings",
                f"{summary.estimated_savings_pct:.1f}%",
                delta="from optimizations",
                delta_color="normal",
            )
        else:
            st.metric("Est. Savings", "-")

    st.divider()

    # Two column layout
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Agent Status")

        # Agent table
        agent_data = []
        for agent in agents:
            status_emoji = {
                AgentStatus.OK: "✅",
                AgentStatus.IDLE: "💤",
                AgentStatus.HOT: "🔥",
                AgentStatus.THROTTLED: "⏸️",
                AgentStatus.ERROR: "❌",
            }.get(agent.status, "❓")

            agent_data.append({
                "Status": status_emoji,
                "Name": agent.name,
                "CPU %": f"{agent.cpu_pct:.1f}",
                "Memory": f"{agent.mem_mb:.0f} MB",
                "Tokens/min": f"{agent.tokens_per_min:.0f}",
                "Latency": f"{agent.avg_latency_ms:.0f} ms",
                "Energy": f"{agent.estimated_energy_score:.2f}" if agent.estimated_energy_score else "-",
                "Last Action": agent.optimizer_action or "-",
            })

        st.dataframe(
            agent_data,
            use_container_width=True,
            hide_index=True,
        )

    with col_right:
        st.subheader("Recent Alerts")

        if alerts:
            for alert in alerts[:5]:
                severity_icon = {
                    "info": "ℹ️",
                    "warning": "⚠️",
                    "critical": "🚨",
                }.get(alert.severity.value, "❓")

                with st.container():
                    st.markdown(f"""
                    **{severity_icon} {alert.agent_id}**

                    {alert.message}

                    *{alert.created_at.strftime('%H:%M:%S')}*
                    """)
                    st.divider()
        else:
            st.success("No active alerts! ✨")

    # Footer
    st.divider()
    st.caption(f"Dashboard URL: {summary.dashboard_url} | TUI: `python -m tamagochi.app`")


if __name__ == "__main__":
    main()
