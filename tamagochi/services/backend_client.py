"""Backend client with REST/WebSocket support and mock fallback.

Provides a unified interface for fetching agent data from either
a real backend or the mock backend.
"""

import asyncio
from datetime import datetime
from typing import AsyncIterator, Optional, Callable, Any
import logging

try:
    import httpx
except ImportError:
    httpx = None

try:
    import websockets
except ImportError:
    websockets = None

from shared.config import settings
from shared.schemas import (
    AgentModel,
    AlertModel,
    BackendStatus,
    CompareModel,
    SummaryModel,
    TimelineEvent,
)
from tamagochi.services.mock_backend import get_mock_backend

logger = logging.getLogger(__name__)


class BackendClient:
    """Client for communicating with the backend API."""

    def __init__(self):
        self._settings = settings()
        self._mock = get_mock_backend()
        self._status = BackendStatus(connected=False, using_mock=True)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ws_connection = None
        self._listeners: list[Callable[[dict], Any]] = []
        self._poll_task: Optional[asyncio.Task] = None

    @property
    def status(self) -> BackendStatus:
        """Get current connection status."""
        return self._status

    @property
    def is_mock_mode(self) -> bool:
        """Check if using mock backend."""
        return self._settings.use_mocks or self._status.using_mock

    async def connect(self) -> bool:
        """Attempt to connect to the real backend."""
        if self._settings.use_mocks:
            self._status = BackendStatus(connected=True, using_mock=True)
            return True

        if httpx is None:
            logger.warning("httpx not installed, using mock backend")
            self._status = BackendStatus(connected=True, using_mock=True)
            return True

        try:
            self._http_client = httpx.AsyncClient(
                base_url=self._settings.backend_url,
                timeout=5.0,
            )
            # Try a health check
            response = await self._http_client.get("/health")
            if response.status_code == 200:
                self._status = BackendStatus(
                    connected=True,
                    using_mock=False,
                    last_ping=datetime.now(),
                )
                return True
        except Exception as e:
            logger.warning(f"Backend connection failed: {e}, falling back to mock")
            self._status = BackendStatus(
                connected=True,
                using_mock=True,
                error=str(e),
            )

        return True  # We can still use mock mode

    async def disconnect(self) -> None:
        """Disconnect from backend."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._ws_connection:
            await self._ws_connection.close()

        if self._http_client:
            await self._http_client.aclose()

        self._status = BackendStatus(connected=False, using_mock=True)

    async def _fetch(self, endpoint: str) -> Optional[dict]:
        """Fetch data from the real backend."""
        if self._http_client is None or self.is_mock_mode:
            return None

        try:
            response = await self._http_client.get(endpoint)
            if response.status_code == 200:
                self._status.last_ping = datetime.now()
                return response.json()
        except Exception as e:
            logger.error(f"Backend fetch error: {e}")
            self._status.error = str(e)

        return None

    # Agent methods
    async def get_agents(self) -> list[AgentModel]:
        """Get all agents."""
        if not self.is_mock_mode:
            data = await self._fetch("/agents")
            if data:
                return [AgentModel(**a) for a in data]

        return self._mock.get_agents()

    async def get_agent(self, agent_id: str) -> Optional[AgentModel]:
        """Get a specific agent."""
        if not self.is_mock_mode:
            data = await self._fetch(f"/agents/{agent_id}")
            if data:
                return AgentModel(**data)

        return self._mock.get_agent(agent_id)

    # Alert methods
    async def get_alerts(self, limit: int = 20) -> list[AlertModel]:
        """Get recent alerts."""
        if not self.is_mock_mode:
            data = await self._fetch(f"/alerts?limit={limit}")
            if data:
                return [AlertModel(**a) for a in data]

        return self._mock.get_alerts(limit)

    # Summary methods
    async def get_summary(self) -> SummaryModel:
        """Get system summary."""
        if not self.is_mock_mode:
            data = await self._fetch("/summary")
            if data:
                return SummaryModel(**data)

        return self._mock.get_summary()

    # Compare methods
    async def get_compare(self, agent_id: str) -> Optional[CompareModel]:
        """Get comparison data for an agent."""
        if not self.is_mock_mode:
            data = await self._fetch(f"/compare/{agent_id}")
            if data:
                return CompareModel(**data)

        return self._mock.get_compare(agent_id)

    # Timeline methods
    async def get_timeline(self, limit: int = 50) -> list[TimelineEvent]:
        """Get timeline events."""
        if not self.is_mock_mode:
            data = await self._fetch(f"/timeline?limit={limit}")
            if data:
                return [TimelineEvent(**e) for e in data]

        return self._mock.get_timeline(limit)

    # Optimization trigger (for demos)
    async def trigger_optimization(self, agent_id: str) -> Optional[CompareModel]:
        """Trigger an optimization event (mock mode only for demos)."""
        if self.is_mock_mode:
            return self._mock.simulate_optimization(agent_id)

        # In real mode, this would POST to the backend
        if self._http_client:
            try:
                response = await self._http_client.post(
                    f"/optimize/{agent_id}",
                    json={"action": "auto"},
                )
                if response.status_code == 200:
                    return CompareModel(**response.json())
            except Exception as e:
                logger.error(f"Optimization trigger failed: {e}")

        return None

    # Telemetry streaming
    def add_listener(self, callback: Callable[[dict], Any]) -> None:
        """Add a listener for telemetry updates."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict], Any]) -> None:
        """Remove a telemetry listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify_listeners(self, data: dict) -> None:
        """Notify all listeners of new data."""
        for listener in self._listeners:
            try:
                result = listener(data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Listener error: {e}")

    async def start_polling(self, interval: Optional[float] = None) -> None:
        """Start polling for updates."""
        if self._poll_task and not self._poll_task.done():
            return

        interval = interval or self._settings.poll_interval
        self._poll_task = asyncio.create_task(self._poll_loop(interval))

    async def _poll_loop(self, interval: float) -> None:
        """Background polling loop."""
        while True:
            try:
                # Tick the mock backend
                if self.is_mock_mode:
                    self._mock.tick()

                # Get latest data
                agents = await self.get_agents()
                summary = await self.get_summary()
                alerts = await self.get_alerts(5)

                # Notify listeners
                await self._notify_listeners({
                    "type": "update",
                    "agents": [a.model_dump() for a in agents],
                    "summary": summary.model_dump(),
                    "alerts": [a.model_dump() for a in alerts],
                })

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(interval)

    async def stream_telemetry(self) -> AsyncIterator[dict]:
        """Stream telemetry updates via WebSocket or polling fallback."""
        if self.is_mock_mode or websockets is None:
            # Fallback to polling
            while True:
                if self.is_mock_mode:
                    self._mock.tick()

                agents = await self.get_agents()
                summary = await self.get_summary()

                yield {
                    "type": "update",
                    "agents": [a.model_dump() for a in agents],
                    "summary": summary.model_dump(),
                }

                await asyncio.sleep(self._settings.poll_interval)
        else:
            # Real WebSocket streaming
            try:
                async with websockets.connect(self._settings.ws_url) as ws:
                    async for message in ws:
                        yield {"type": "update", "data": message}
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                # Fall back to polling
                async for data in self.stream_telemetry():
                    yield data


# Singleton instance
_client: Optional[BackendClient] = None


def get_backend_client() -> BackendClient:
    """Get or create the backend client singleton."""
    global _client
    if _client is None:
        _client = BackendClient()
    return _client
