"""Agents page - Detailed agent information."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.schemas import AgentStatus

st.set_page_config(page_title="Agents - Mochi", page_icon="🤖", layout="wide")

st.title("🤖 Agent Details")
st.caption("Individual agent metrics and status")


def get_mock_data():
    """Get mock data."""
    from tamagochi.services.mock_backend import get_mock_backend
    mock = get_mock_backend()
    for _ in range(2):
        mock.tick()
    return mock.get_agents()


agents = get_mock_data()

# Agent selector
agent_names = {a.agent_id: a.name for a in agents}
selected_id = st.selectbox(
    "Select Agent",
    options=list(agent_names.keys()),
    format_func=lambda x: f"{agent_names[x]} ({x})",
)

selected_agent = next((a for a in agents if a.agent_id == selected_id), None)

if selected_agent:
    st.divider()

    # Status header
    status_emoji = {
        AgentStatus.OK: "✅",
        AgentStatus.IDLE: "💤",
        AgentStatus.HOT: "🔥",
        AgentStatus.THROTTLED: "⏸️",
        AgentStatus.ERROR: "❌",
    }.get(selected_agent.status, "❓")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(f"{status_emoji} {selected_agent.name}")
        st.caption(f"ID: {selected_agent.agent_id}")
    with col2:
        st.metric("Status", selected_agent.status.value.upper())

    st.divider()

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cpu_delta = "High" if selected_agent.cpu_pct > 75 else ("Normal" if selected_agent.cpu_pct > 25 else "Low")
        st.metric("CPU Usage", f"{selected_agent.cpu_pct:.1f}%", delta=cpu_delta,
                  delta_color="inverse" if selected_agent.cpu_pct > 75 else "off")

    with col2:
        st.metric("Memory", f"{selected_agent.mem_mb:.0f} MB")

    with col3:
        st.metric("Tokens/min", f"{selected_agent.tokens_per_min:.0f}")

    with col4:
        st.metric("Latency", f"{selected_agent.avg_latency_ms:.0f} ms")

    st.divider()

    # Detailed metrics
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Resource Utilization")

        # Gauge chart for CPU
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=selected_agent.cpu_pct,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "CPU %"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#667eea"},
                'steps': [
                    {'range': [0, 50], 'color': "#E8F5E9"},
                    {'range': [50, 75], 'color': "#FFF3E0"},
                    {'range': [75, 100], 'color': "#FFEBEE"},
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 75
                }
            }
        ))
        fig.update_layout(height=250, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Token Activity")

        # Token in/out breakdown
        fig = px.pie(
            values=[selected_agent.tokens_in, selected_agent.tokens_out],
            names=["Input", "Output"],
            color_discrete_sequence=["#667eea", "#764ba2"],
            hole=0.5,
        )
        fig.update_layout(height=250, margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    # Additional info
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Environment")
        if selected_agent.temp_c:
            st.write(f"🌡️ Temperature: {selected_agent.temp_c:.1f}°C")
        if selected_agent.estimated_energy_score:
            score = selected_agent.estimated_energy_score
            efficiency = "🟢 Efficient" if score < 0.4 else ("🟡 Moderate" if score < 0.7 else "🔴 High usage")
            st.write(f"⚡ Energy Score: {score:.2f} ({efficiency})")

    with col2:
        st.subheader("Optimizer")
        if selected_agent.optimizer_action:
            st.success(f"✅ Last action: {selected_agent.optimizer_action}")
        else:
            st.info("No optimization actions yet")

        st.caption(f"Last updated: {selected_agent.last_updated.strftime('%H:%M:%S')}")
