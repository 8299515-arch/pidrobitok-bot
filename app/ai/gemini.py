from __future__ import annotations

from google import genai
from google.genai import types

from app.ai.provider import AIMessage


class GeminiProvider:
    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: genai.Client | None = None

    async def generate(self, messages: list[AIMessage], *, system_instruction: str) -> str:
        if not self._api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part(text=message.content)],
            )
            for message in messages
        ]
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
        )
        return (response.text or "").strip()

    async def health(self) -> bool:
        return bool(self._api_key and self._model)
