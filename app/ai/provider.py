from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AIMessage:
    role: str
    content: str


class AIProvider(Protocol):
    async def generate(self, messages: list[AIMessage], *, system_instruction: str) -> str:
        """Generate a response from untrusted user/source data under system policy."""

    async def health(self) -> bool:
        """Return whether the provider is configured and reachable enough to use."""
