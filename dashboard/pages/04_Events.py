"""Events page - Timeline of system events."""

import streamlit as st
import plotly.express as px
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Events - Mochi", page_icon="📋", layout="wide")

st.title("📋 Events & Timeline")
st.caption("System events, alerts, and optimization history")


def get_mock_data():
    """Get mock data."""
    from tamagochi.services.mock_backend import get_mock_backend
    mock = get_mock_backend()

    # Generate some activity
    for _ in range(5):
        mock.tick()

    # Trigger an optimization to generate events
    agents = mock.get_agents()
    if agents:
        mock.simulate_optimization(agents[0].agent_id)

    return {
        "alerts": mock.get_alerts(),
        "timeline": mock.get_timeline(),
    }


data = get_mock_data()
alerts = data["alerts"]
timeline = data["timeline"]

# Tabs for different views
tab1, tab2 = st.tabs(["📢 Alerts", "📅 Timeline"])

with tab1:
    st.subheader("Active Alerts")

    if alerts:
        # Filter options
        col1, col2 = st.columns([1, 3])
        with col1:
            severity_filter = st.multiselect(
                "Filter by severity",
                ["critical", "warning", "info"],
                default=["critical", "warning", "info"],
            )

        filtered_alerts = [a for a in alerts if a.severity.value in severity_filter]

        if filtered_alerts:
            for alert in filtered_alerts:
                severity_colors = {
                    "critical": "🚨",
                    "warning": "⚠️",
                    "info": "ℹ️",
                }
                severity_bg = {
                    "critical": "#FFEBEE",
                    "warning": "#FFF3E0",
                    "info": "#E3F2FD",
                }

                icon = severity_colors.get(alert.severity.value, "❓")
                bg = severity_bg.get(alert.severity.value, "#FFFFFF")

                with st.container():
                    st.markdown(f"""
                    <div style="background-color: {bg}; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem;">
                        <strong>{icon} {alert.agent_id}</strong><br/>
                        {alert.message}<br/>
                        <small style="color: #666;">{alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}</small>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No alerts match the filter.")
    else:
        st.success("🎉 No active alerts! System is running smoothly.")

with tab2:
    st.subheader("Event Timeline")

    if timeline:
        # Event type filter
        event_types = list(set(e.event_type for e in timeline))
        selected_types = st.multiselect(
            "Filter by event type",
            event_types,
            default=event_types,
        )

        filtered_events = [e for e in timeline if e.event_type in selected_types]

        if filtered_events:
            # Timeline visualization
            for event in filtered_events[:20]:
                event_icons = {
                    "optimization": "⚡",
                    "alert": "⚠️",
                    "throttle": "⏸️",
                    "error": "❌",
                }
                icon = event_icons.get(event.event_type, "📌")

                col1, col2 = st.columns([1, 4])
                with col1:
                    st.caption(event.timestamp.strftime('%H:%M:%S'))
                with col2:
                    agent_badge = f"[{event.agent_id}]" if event.agent_id else ""
                    st.write(f"{icon} **{event.event_type}** {agent_badge}")
                    st.caption(event.description)

                st.divider()
        else:
            st.info("No events match the filter.")
    else:
        st.info("No events recorded yet. Use the TUI to interact with agents.")

# Stats
st.divider()
st.subheader("📊 Event Statistics")

col1, col2, col3 = st.columns(3)

with col1:
    critical_count = len([a for a in alerts if a.severity.value == "critical"])
    st.metric("Critical Alerts", critical_count)

with col2:
    opt_count = len([e for e in timeline if e.event_type == "optimization"])
    st.metric("Optimizations", opt_count)

with col3:
    st.metric("Total Events", len(timeline))

# Event type distribution
if timeline:
    st.subheader("Event Distribution")
    event_counts = {}
    for event in timeline:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

    fig = px.pie(
        values=list(event_counts.values()),
        names=list(event_counts.keys()),
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)
