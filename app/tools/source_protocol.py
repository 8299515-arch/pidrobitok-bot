from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from app.domain.jobs import Job


class JobSourceTool(Protocol):
    """Contract implemented by every vacancy source adapter."""

    @property
    def name(self) -> str:
        ...

    async def search(self, query: str, *, location: str | None = None) -> Sequence[Job]:
        ...

    async def health(self) -> Mapping[str, object]:
        ...
