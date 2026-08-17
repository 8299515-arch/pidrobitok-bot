from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    google_api_key: str
    ai_model: str = "gemini-1.5-flash"
    max_history_messages: int = 12

    @classmethod
    def from_environment(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()

        if not bot_token:
            raise RuntimeError("BOT_TOKEN is not configured")
        if not google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        return cls(
            bot_token=bot_token,
            google_api_key=google_api_key,
            ai_model=os.getenv("AI_MODEL", "gemini-1.5-flash").strip(),
        )
