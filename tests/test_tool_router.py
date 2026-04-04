"""Tests for tool router."""

import pytest
import asyncio

from shared.schemas import AgentStatus
from tamagochi.services.tool_router import ToolRouter, get_tool_router
from tamagochi.services.mock_backend import MockBackend
from tamagochi.services.backend_client import BackendClient


class TestToolRouter:
    """Tests for ToolRouter."""

    @pytest.fixture
    def router(self):
        """Create a router with mock backend."""
        client = BackendClient()
        # Force mock mode
        client._status.using_mock = True
        return ToolRouter(client)

    @pytest.mark.asyncio
    async def test_list_agents(self, router):
        """Test listing agents."""
        agents = await router.call_tool("list_agents")

        assert len(agents) > 0
        assert all(hasattr(a, 'agent_id') for a in agents)

    @pytest.mark.asyncio
    async def test_get_agent(self, router):
        """Test getting a specific agent."""
        agent = await router.call_tool("get_agent", agent_id="camera-agent")

        assert agent is not None
        assert agent.agent_id == "camera-agent"

    @pytest.mark.asyncio
    async def test_get_summary(self, router):
        """Test getting summary."""
        summary = await router.call_tool("get_summary")

        assert summary is not None
        assert hasattr(summary, 'active_agents')

    @pytest.mark.asyncio
    async def test_get_alerts(self, router):
        """Test getting alerts."""
        alerts = await router.call_tool("get_alerts")

        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_route_agents_command(self, router):
        """Test routing /agents command."""
        result = await router.route_command("/agents", [])

        assert result.success is True
        assert "Agent" in result.output or "agent" in result.output

    @pytest.mark.asyncio
    async def test_route_inspect_command(self, router):
        """Test routing /inspect command."""
        result = await router.route_command("/inspect", ["camera-agent"])

        assert result.success is True
        assert "camera-agent" in result.output.lower() or "Camera" in result.output

    @pytest.mark.asyncio
    async def test_route_inspect_missing_arg(self, router):
        """Test /inspect command without agent ID."""
        result = await router.route_command("/inspect", [])

        assert result.success is False
        assert "Usage" in result.error

    @pytest.mark.asyncio
    async def test_route_summary_command(self, router):
        """Test routing /summary command."""
        result = await router.route_command("/summary", [])

        assert result.success is True
        assert "agents" in result.output.lower()

    @pytest.mark.asyncio
    async def test_route_unknown_command(self, router):
        """Test routing unknown command."""
        result = await router.route_command("/unknown", [])

        assert result.success is False
        assert "Unknown command" in result.error

    @pytest.mark.asyncio
    async def test_route_optimize_command(self, router):
        """Test routing /optimize command."""
        result = await router.route_command("/optimize", ["camera-agent"])

        assert result.success is True
        assert "Optimized" in result.output or "comparison" in str(result.data)

    def test_list_tools(self, router):
        """Test listing available tools."""
        tools = router.list_tools()

        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "list_agents" in tool_names
        assert "get_agent" in tool_names
        assert "get_summary" in tool_names

    def test_get_tool(self, router):
        """Test getting a specific tool definition."""
        tool = router.get_tool("list_agents")

        assert tool is not None
        assert tool.name == "list_agents"
        assert tool.description is not None

    def test_get_nonexistent_tool(self, router):
        """Test getting a tool that doesn't exist."""
        tool = router.get_tool("nonexistent")

        assert tool is None

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, router):
        """Test calling an unknown tool raises error."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await router.call_tool("nonexistent_tool")


class TestToolRouterFormatters:
    """Tests for tool router formatting methods."""

    @pytest.fixture
    def router(self):
        """Create a router."""
        return ToolRouter()

    @pytest.mark.asyncio
    async def test_format_agents_list(self, router):
        """Test agents list formatting."""
        agents = await router.call_tool("list_agents")
        output = router._format_agents_list(agents)

        assert "Agents" in output
        assert "CPU" in output or "cpu" in output.lower()

    @pytest.mark.asyncio
    async def test_format_summary(self, router):
        """Test summary formatting."""
        summary = await router.call_tool("get_summary")
        output = router._format_summary(summary)

        assert "Summary" in output
        assert "agents" in output.lower()
