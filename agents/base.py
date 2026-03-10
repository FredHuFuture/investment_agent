from __future__ import annotations

from abc import ABC, abstractmethod

from agents.models import AgentInput, AgentOutput
from data_providers.base import DataProvider


class BaseAgent(ABC):
    """Abstract base class for analysis agents."""

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name."""

    @abstractmethod
    def supported_asset_types(self) -> list[str]:
        """Return supported asset types."""

    @abstractmethod
    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        """Run analysis and return output."""

    def _validate_asset_type(self, agent_input: AgentInput) -> None:
        if agent_input.asset_type not in self.supported_asset_types():
            raise NotImplementedError(
                f"{self.name} does not support '{agent_input.asset_type}'. "
                f"Supported: {self.supported_asset_types()}"
            )

    def _clamp_confidence(self, value: float) -> float:
        return max(0.0, min(100.0, value))
