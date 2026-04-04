"""Overview page - System-wide metrics and status."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.schemas import AgentStatus

st.set_page_config(page_title="Overview - Mochi", page_icon="📊", layout="wide")

st.title("📊 System Overview")
st.caption("Real-time metrics and performance indicators")


def get_mock_data():
    """Get mock data."""
    from tamagochi.services.mock_backend import get_mock_backend
    mock = get_mock_backend()
    for _ in range(2):
        mock.tick()
    return {
        "agents": mock.get_agents(),
        "summary": mock.get_summary(),
    }


data = get_mock_data()
agents = data["agents"]
summary = data["summary"]

# Metrics row
col1, col2, col3, col4 = st.columns(4)

with col1:
    hot_pct = (summary.hot_agents / summary.active_agents * 100) if summary.active_agents > 0 else 0
    st.metric("System Health", f"{100 - hot_pct:.0f}%", delta=f"{summary.hot_agents} hot" if summary.hot_agents > 0 else "All good")

with col2:
    st.metric("Total Agents", summary.active_agents)

with col3:
    st.metric("Token Rate", f"{summary.tokens_per_min_total:,.0f}/min")

with col4:
    if summary.estimated_energy_score_total:
        score = summary.estimated_energy_score_total
        label = "Good" if score < 0.4 else ("Moderate" if score < 0.7 else "High")
        st.metric("Energy Score", f"{score:.2f}", delta=label)
    else:
        st.metric("Energy Score", "-")

st.divider()

# Charts
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Agent Status Distribution")

    status_counts = {}
    for agent in agents:
        status = agent.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    fig = px.pie(
        values=list(status_counts.values()),
        names=list(status_counts.keys()),
        color=list(status_counts.keys()),
        color_discrete_map={
            "ok": "#4CAF50",
            "idle": "#9E9E9E",
            "hot": "#f44336",
            "throttled": "#FF9800",
            "error": "#E91E63",
        },
        hole=0.4,
    )
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Resource Usage by Agent")

    agent_names = [a.name[:15] for a in agents]
    cpu_values = [a.cpu_pct for a in agents]
    token_values = [a.tokens_per_min / 100 for a in agents]  # Scale for visibility

    fig = go.Figure()
    fig.add_trace(go.Bar(name='CPU %', x=agent_names, y=cpu_values, marker_color='#667eea'))
    fig.add_trace(go.Bar(name='Tokens/100', x=agent_names, y=token_values, marker_color='#764ba2'))
    fig.update_layout(
        barmode='group',
        margin=dict(t=20, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Time series (mock historical data)
st.subheader("Token Usage Over Time")

# Generate mock time series
times = [datetime.now() - timedelta(minutes=i*5) for i in range(12, 0, -1)]
token_history = [summary.tokens_per_min_total * (0.8 + random.uniform(0, 0.4)) for _ in times]

fig = px.line(
    x=times,
    y=token_history,
    labels={"x": "Time", "y": "Tokens/min"},
)
fig.update_traces(line_color='#4CAF50', line_width=3)
fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
st.plotly_chart(fig, use_container_width=True)
