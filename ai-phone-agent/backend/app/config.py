"""
Application configuration manager.

Uses pydantic-settings to load configuration from environment variables
with sensible defaults. Falls back to .env file for local development.
"""

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

# Load .env file if present (for local development)
# In production, env vars should be injected by the deployment platform
load_dotenv()


class Settings:
    """Application settings loaded from environment variables.

    All configuration is centralized here to avoid scattered os.getenv calls
    throughout the codebase. This makes it trivial to see what the app needs
    to run and to swap providers by just changing env vars.
    """

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # --- Vobiz Telephony ---
    VOBIZ_API_KEY: str = os.getenv("VOBIZ_API_KEY", "")
    VOBIZ_BASE_URL: str = os.getenv("VOBIZ_BASE_URL", "https://api.vobiz.com/v1")

    # --- Sarvam AI (Voice STT/TTS) ---
    SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")
    SARVAM_BASE_URL: str = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai/v1")

    # --- LLM Provider Selection ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower()

    # --- Groq ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.7"))
    GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "512"))

    # --- OpenAI ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "512"))

    # --- Anthropic ---
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    ANTHROPIC_TEMPERATURE: float = float(os.getenv("ANTHROPIC_TEMPERATURE", "0.7"))
    ANTHROPIC_MAX_TOKENS: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "512"))

    # --- DeepSeek ---
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    DEEPSEEK_TEMPERATURE: float = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))
    DEEPSEEK_MAX_TOKENS: int = int(os.getenv("DEEPSEEK_MAX_TOKENS", "512"))

    # --- Redis ---
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL") or None
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))

    # --- Business Context (injected into prompts) ---
    BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "Your Business")
    BUSINESS_TYPE: str = os.getenv("BUSINESS_TYPE", "coaching")
    AGENT_LANGUAGE: str = os.getenv("AGENT_LANGUAGE", "hi-IN")
    BATTLE_CARD_TEXT: str = os.getenv(
        "BATTLE_CARD_TEXT",
        "You are a helpful phone assistant for a coaching business.",
    )

    def provider_config(self, provider_name: str) -> dict:
        """Return configuration dict for a named LLM provider.

        Args:
            provider_name: One of 'groq', 'openai', 'anthropic', 'deepseek'

        Returns:
            Dict with api_key, model, temperature, max_tokens, base_url
        """
        configs = {
            "groq": {
                "api_key": self.GROQ_API_KEY,
                "model": self.GROQ_MODEL,
                "temperature": self.GROQ_TEMPERATURE,
                "max_tokens": self.GROQ_MAX_TOKENS,
                "base_url": "https://api.groq.com/openai/v1",
                "timeout_seconds": 10,
            },
            "openai": {
                "api_key": self.OPENAI_API_KEY,
                "model": self.OPENAI_MODEL,
                "temperature": self.OPENAI_TEMPERATURE,
                "max_tokens": self.OPENAI_MAX_TOKENS,
                "base_url": "https://api.openai.com/v1",
                "timeout_seconds": 15,
            },
            "anthropic": {
                "api_key": self.ANTHROPIC_API_KEY,
                "model": self.ANTHROPIC_MODEL,
                "temperature": self.ANTHROPIC_TEMPERATURE,
                "max_tokens": self.ANTHROPIC_MAX_TOKENS,
                "base_url": "https://api.anthropic.com/v1",
                "timeout_seconds": 20,
            },
            "deepseek": {
                "api_key": self.DEEPSEEK_API_KEY,
                "model": self.DEEPSEEK_MODEL,
                "temperature": self.DEEPSEEK_TEMPERATURE,
                "max_tokens": self.DEEPSEEK_MAX_TOKENS,
                "base_url": "https://api.deepseek.com/v1",
                "timeout_seconds": 30,
            },
        }
        return configs.get(provider_name, configs["groq"])


@lru_cache()
def get_settings() -> Settings:
    """Return a singleton Settings instance.

    Using lru_cache ensures we only read env vars once at startup,
    avoiding repeated os.getenv overhead on every request.
    """
    return Settings()
