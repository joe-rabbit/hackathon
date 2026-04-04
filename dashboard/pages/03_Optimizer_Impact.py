"""Optimizer Impact page - Before/after comparisons."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Optimizer Impact - Mochi", page_icon="⚡", layout="wide")

st.title("⚡ Optimizer Impact")
st.caption("Before and after optimization comparisons")


def get_mock_data():
    """Get mock data with some optimizations."""
    from tamagochi.services.mock_backend import get_mock_backend
    mock = get_mock_backend()

    # Simulate some optimizations
    agents = mock.get_agents()
    hot_agents = [a for a in agents if a.status.value == "hot"]

    comparisons = []
    for agent in hot_agents[:2]:  # Optimize first 2 hot agents
        comparison = mock.simulate_optimization(agent.agent_id)
        if comparison:
            comparisons.append(comparison)

    return {
        "comparisons": comparisons,
        "agents": mock.get_agents(),
    }


data = get_mock_data()
comparisons = data["comparisons"]

if not comparisons:
    st.info("No optimization data available yet. Run `/optimize <agent_id>` in the TUI to generate data.")

    # Show a sample of what it would look like
    st.subheader("Sample Optimization View")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("CPU Before", "82.5%")
        st.metric("CPU After", "45.2%", delta="-37.3%", delta_color="normal")
    with col2:
        st.metric("Tokens Before", "1850/min")
        st.metric("Tokens After", "980/min", delta="-870", delta_color="normal")
    with col3:
        st.metric("Energy Before", "0.81")
        st.metric("Energy After", "0.42", delta="-48%", delta_color="normal")

else:
    for comparison in comparisons:
        st.subheader(f"🎯 {comparison.agent_id}")

        with st.container():
            # Metrics comparison
            col1, col2, col3, col4 = st.columns(4)

            # CPU
            cpu_change = comparison.after.cpu_pct - comparison.before.cpu_pct
            with col1:
                st.metric(
                    "CPU",
                    f"{comparison.after.cpu_pct:.1f}%",
                    delta=f"{cpu_change:+.1f}%",
                    delta_color="normal" if cpu_change < 0 else "inverse",
                )

            # Tokens
            token_change = comparison.after.tokens_per_min - comparison.before.tokens_per_min
            with col2:
                st.metric(
                    "Tokens/min",
                    f"{comparison.after.tokens_per_min:.0f}",
                    delta=f"{token_change:+.0f}",
                    delta_color="normal" if token_change < 0 else "inverse",
                )

            # Latency
            latency_change = comparison.after.avg_latency_ms - comparison.before.avg_latency_ms
            with col3:
                st.metric(
                    "Latency",
                    f"{comparison.after.avg_latency_ms:.0f} ms",
                    delta=f"{latency_change:+.0f} ms",
                    delta_color="normal" if latency_change < 0 else "inverse",
                )

            # Energy
            if comparison.before.estimated_energy_score and comparison.after.estimated_energy_score:
                energy_change = comparison.after.estimated_energy_score - comparison.before.estimated_energy_score
                energy_pct = (energy_change / comparison.before.estimated_energy_score) * 100
                with col4:
                    st.metric(
                        "Energy Score",
                        f"{comparison.after.estimated_energy_score:.2f}",
                        delta=f"{energy_pct:+.1f}%",
                        delta_color="normal" if energy_change < 0 else "inverse",
                    )

            # Bar chart comparison
            st.divider()

            fig = go.Figure()

            metrics = ['CPU %', 'Tokens (scaled)', 'Latency (scaled)', 'Energy×100']
            before_vals = [
                comparison.before.cpu_pct,
                comparison.before.tokens_per_min / 50,  # Scale
                comparison.before.avg_latency_ms / 10,  # Scale
                (comparison.before.estimated_energy_score or 0) * 100,
            ]
            after_vals = [
                comparison.after.cpu_pct,
                comparison.after.tokens_per_min / 50,
                comparison.after.avg_latency_ms / 10,
                (comparison.after.estimated_energy_score or 0) * 100,
            ]

            fig.add_trace(go.Bar(
                name='Before',
                x=metrics,
                y=before_vals,
                marker_color='#f44336',
                opacity=0.7,
            ))
            fig.add_trace(go.Bar(
                name='After',
                x=metrics,
                y=after_vals,
                marker_color='#4CAF50',
                opacity=0.7,
            ))

            fig.update_layout(
                barmode='group',
                title='Before vs After Optimization',
                margin=dict(t=50, b=20, l=20, r=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )

            st.plotly_chart(fig, use_container_width=True)

            # Explanation facts
            if comparison.explanation_facts:
                st.subheader("What happened")
                for fact in comparison.explanation_facts:
                    st.write(f"• {fact}")

            st.divider()

# Summary
st.divider()
st.subheader("📈 Total Impact")

if comparisons:
    total_cpu_saved = sum(c.before.cpu_pct - c.after.cpu_pct for c in comparisons)
    total_tokens_saved = sum(c.before.tokens_per_min - c.after.tokens_per_min for c in comparisons)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total CPU Saved", f"{total_cpu_saved:.1f}%")
    with col2:
        st.metric("Total Tokens Saved", f"{total_tokens_saved:.0f}/min")
    with col3:
        st.metric("Agents Optimized", len(comparisons))
else:
    st.info("Optimize some agents to see impact metrics here.")
