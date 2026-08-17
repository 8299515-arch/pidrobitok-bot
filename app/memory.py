from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class ConversationMemory:
    def __init__(self, max_messages: int = 12) -> None:
        self._messages: dict[int, deque[Message]] = defaultdict(
            lambda: deque(maxlen=max_messages)
        )

    def add(self, user_id: int, role: str, content: str) -> None:
        self._messages[user_id].append(Message(role=role, content=content))

    def history(self, user_id: int) -> list[Message]:
        return list(self._messages[user_id])

    def clear(self, user_id: int) -> None:
        self._messages.pop(user_id, None)
