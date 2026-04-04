"""Shared Pydantic schemas for Mochi UI and Dashboard.

These schemas define the contract between the backend, TUI, and dashboard.
All components use the same models for consistency.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent operational status."""
    OK = "ok"
    IDLE = "idle"
    HOT = "hot"
    THROTTLED = "throttled"
    ERROR = "error"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MochiMood(str, Enum):
    """Mochi's emotional states."""
    IDLE = "idle"
    THINKING = "thinking"
    HAPPY = "happy"
    WARNING = "warning"
    SLEEPY = "sleepy"
    CELEBRATE = "celebrate"
    SICK = "sick"


class AgentModel(BaseModel):
    """Model representing an AI agent's current state."""
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable agent name")
    status: AgentStatus = Field(default=AgentStatus.OK, description="Current status")
    cpu_pct: float = Field(default=0.0, ge=0, le=100, description="CPU usage percentage")
    mem_mb: float = Field(default=0.0, ge=0, description="Memory usage in MB")
    temp_c: Optional[float] = Field(default=None, description="Temperature in Celsius")
    tokens_in: int = Field(default=0, ge=0, description="Input tokens processed")
    tokens_out: int = Field(default=0, ge=0, description="Output tokens generated")
    tokens_per_min: float = Field(default=0.0, ge=0, description="Token throughput")
    avg_latency_ms: float = Field(default=0.0, ge=0, description="Average response latency")
    optimizer_action: Optional[str] = Field(default=None, description="Last optimizer action")
    estimated_energy_score: Optional[float] = Field(default=None, description="Energy efficiency score 0-1")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    @property
    def is_hot(self) -> bool:
        """Check if agent is in hot state."""
        return self.status == AgentStatus.HOT

    @property
    def is_wasteful(self) -> bool:
        """Check if agent shows signs of waste."""
        return (
            self.cpu_pct > 80
            or self.tokens_per_min > 2000
            or (self.estimated_energy_score is not None and self.estimated_energy_score > 0.7)
        )


class AlertModel(BaseModel):
    """Model representing a system alert."""
    id: str = Field(..., description="Unique alert identifier")
    agent_id: str = Field(..., description="Related agent ID")
    severity: AlertSeverity = Field(default=AlertSeverity.INFO)
    message: str = Field(..., description="Alert message")
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def is_critical(self) -> bool:
        return self.severity == AlertSeverity.CRITICAL


class SummaryModel(BaseModel):
    """System-wide summary metrics."""
    active_agents: int = Field(default=0, ge=0)
    hot_agents: int = Field(default=0, ge=0)
    alerts_open: int = Field(default=0, ge=0)
    tokens_per_min_total: float = Field(default=0.0, ge=0)
    estimated_energy_score_total: Optional[float] = Field(default=None)
    estimated_savings_pct: Optional[float] = Field(default=None)
    dashboard_url: str = Field(default="http://127.0.0.1:8501")


class MetricSnapshot(BaseModel):
    """Snapshot of metrics at a point in time."""
    cpu_pct: float = Field(default=0.0)
    tokens_per_min: float = Field(default=0.0)
    avg_latency_ms: float = Field(default=0.0)
    estimated_energy_score: Optional[float] = Field(default=None)


class CompareModel(BaseModel):
    """Before/after comparison for optimizer impact."""
    agent_id: str = Field(..., description="Agent being compared")
    before: MetricSnapshot = Field(..., description="Metrics before optimization")
    after: MetricSnapshot = Field(..., description="Metrics after optimization")
    explanation_facts: list[str] = Field(default_factory=list, description="Facts about the change")

    @property
    def cpu_improvement(self) -> float:
        """Calculate CPU improvement percentage."""
        if self.before.cpu_pct == 0:
            return 0.0
        return ((self.before.cpu_pct - self.after.cpu_pct) / self.before.cpu_pct) * 100

    @property
    def token_improvement(self) -> float:
        """Calculate token throughput improvement."""
        if self.before.tokens_per_min == 0:
            return 0.0
        return ((self.before.tokens_per_min - self.after.tokens_per_min) / self.before.tokens_per_min) * 100


class TimelineEvent(BaseModel):
    """Event in the system timeline."""
    id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str = Field(..., description="Type: optimization, alert, throttle, etc.")
    agent_id: Optional[str] = Field(default=None)
    description: str
    data: Optional[dict] = Field(default=None, description="Additional event data")


class LLMExplanation(BaseModel):
    """Structured output from the local LLM."""
    summary: str = Field(..., description="One-line summary in Mochi voice")
    culprit_agent: Optional[str] = Field(default=None, description="Agent causing issue")
    problem: str = Field(..., description="What went wrong or what was asked")
    optimizer_effect: Optional[str] = Field(default=None, description="What the optimizer did")
    evidence: list[str] = Field(default_factory=list, description="Supporting facts")
    confidence: str = Field(default="medium", description="low, medium, or high")


class CommandResult(BaseModel):
    """Result of a slash command execution."""
    success: bool = True
    command: str
    output: str
    data: Optional[dict] = Field(default=None)
    error: Optional[str] = Field(default=None)


class BackendStatus(BaseModel):
    """Backend connection status."""
    connected: bool = False
    using_mock: bool = True
    last_ping: Optional[datetime] = None
    error: Optional[str] = None
