"""
Application configuration manager.

Uses pydantic-settings to load configuration from environment variables
with sensible defaults. Falls back to .env file for local development.
"""

from __future__ import annotations

import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file if present (for local development)
# In production, env vars should be injected by the deployment platform
load_dotenv()


# ---------------------------------------------------------------------------
# DEMO_MODE control
# ---------------------------------------------------------------------------

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
DEMO_WHITELIST_NUMBERS = set(
    n.strip() for n in os.getenv("DEMO_WHITELIST_NUMBERS", "").split(",") if n.strip()
)


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
    VOBIZ_AUTH_ID: str = os.getenv("VOBIZ_AUTH_ID", "")
    VOBIZ_AUTH_TOKEN: str = os.getenv("VOBIZ_AUTH_TOKEN", "")
    VOBIZ_BASE_URL: str = os.getenv("VOBIZ_BASE_URL", "https://api.vobiz.ai/api/v1")

    # --- Sarvam AI (Voice STT/TTS) ---
    SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")
    SARVAM_BASE_URL: str = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")

    # --- LLM Provider Selection ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic").lower()

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
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    ANTHROPIC_TEMPERATURE: float = float(os.getenv("ANTHROPIC_TEMPERATURE", "0.7"))
    ANTHROPIC_MAX_TOKENS: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "512"))

    # --- DeepSeek ---
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    DEEPSEEK_TEMPERATURE: float = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))
    DEEPSEEK_MAX_TOKENS: int = int(os.getenv("DEEPSEEK_MAX_TOKENS", "512"))

    # --- xAI Grok ---
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    XAI_MODEL: str = os.getenv("XAI_MODEL", "grok-2-1212")
    XAI_TEMPERATURE: float = float(os.getenv("XAI_TEMPERATURE", "0.7"))
    XAI_MAX_TOKENS: int = int(os.getenv("XAI_MAX_TOKENS", "150"))

    # --- Redis ---
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL") or None
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))

    # --- Cal.com ---
    CAL_API_KEY: str = os.getenv("CAL_API_KEY", "")
    CAL_USERNAME: str = os.getenv("CAL_USERNAME", "")
    CAL_EVENT_SLUG: str = os.getenv("CAL_EVENT_SLUG", "")

    # --- Business Context (injected into prompts) ---
    BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "Your Business")
    BUSINESS_TYPE: str = os.getenv("BUSINESS_TYPE", "coaching")
    AGENT_LANGUAGE: str = os.getenv("AGENT_LANGUAGE", "en-IN")
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
            "xai": {
                "api_key": self.XAI_API_KEY,
                "model": self.XAI_MODEL,
                "temperature": self.XAI_TEMPERATURE,
                "max_tokens": self.XAI_MAX_TOKENS,
                "base_url": "https://api.x.ai/v1",
                "timeout_seconds": 10,
            },
        }
        return configs.get(provider_name, configs.get("anthropic", configs["xai"]))


@lru_cache()
def get_settings() -> Settings:
    """Return a singleton Settings instance.

    Using lru_cache ensures we only read env vars once at startup,
    avoiding repeated os.getenv overhead on every request.
    """
    return Settings()


# ---------------------------------------------------------------------------
# Context layer — per-module markdown files loaded once at import
# ---------------------------------------------------------------------------

CONTEXT_DIR = Path(__file__).parent.parent / "context"

PERSONA = (CONTEXT_DIR / "persona.md").read_text()
BATTLE_CARD = (CONTEXT_DIR / "battle_card.md").read_text()
OBJECTIONS = (CONTEXT_DIR / "objections.md").read_text()
STATE_PROMPTS = (CONTEXT_DIR / "state_prompts.md").read_text()
MEMORY_SCHEMA = (CONTEXT_DIR / "memory_schema.md").read_text()
VOICE_PERSONA = (CONTEXT_DIR / "voice_persona.md").read_text()
WHATSAPP_PERSONA = (CONTEXT_DIR / "whatsapp_persona.md").read_text()
CALENDAR_RULES = (CONTEXT_DIR / "calendar_rules.md").read_text()
COMPLIANCE = (CONTEXT_DIR / "compliance.md").read_text()
EVAL_CASES = (CONTEXT_DIR / "eval_cases.md").read_text()

with open(CONTEXT_DIR / "banned_phrases.json") as _f:
    BANNED_PHRASES = json.load(_f)
BANNED_FLAT = [p for cat in BANNED_PHRASES.values() for p in cat]

# Language policy
LANGUAGE_POLICY_INSTRUCTION = (
    "Respond in English only. Do not use Hindi, Hinglish, transliteration, "
    "or any other language. If the lead speaks another language, follow "
    "the language-switch script in the persona."
)

# Non-Latin script regex (Devanagari, Tamil, Telugu, Bengali)
NON_ENGLISH_SCRIPT_PATTERN = re.compile(
    r"[\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0980-\u09FF]"
)


# ---------------------------------------------------------------------------
# Production-mode demo-tag guard
# ---------------------------------------------------------------------------

def _enforce_no_demo_in_production() -> None:
    if DEMO_MODE:
        return
    offenders = []
    for md_file in CONTEXT_DIR.glob("*.md"):
        text = md_file.read_text()
        if "[DEMO:" in text:
            offenders.append(str(md_file.name))
    if offenders:
        print(
            "FATAL: DEMO_MODE=false but [DEMO:] tags still present in context files:\n  "
            + "\n  ".join(offenders),
            file=sys.stderr,
        )
        sys.exit(1)


_enforce_no_demo_in_production()


# ---------------------------------------------------------------------------
# Outbound call routing guard
# ---------------------------------------------------------------------------

def _normalize_phone(phone: str) -> str:
    """Strip formatting chars for comparison."""
    return phone.strip().replace(" ", "").replace("-", "").lstrip("+")


# Pre-normalize whitelist for fast comparison
_NORMALIZED_WHITELIST = {_normalize_phone(n) for n in DEMO_WHITELIST_NUMBERS}


def can_call(phone_number: str) -> tuple[bool, str]:
    """Return whether the agent is allowed to call *phone_number*.

    In DEMO_MODE, only whitelisted numbers are permitted.
    In production, additional checks (DNC, consent) should be added.
    """
    if DEMO_MODE:
        if _normalize_phone(phone_number) not in _NORMALIZED_WHITELIST:
            return False, f"DEMO_MODE: {phone_number} not in whitelist"
        return True, "DEMO_MODE: whitelisted"
    # Production checks: DNC list, consent records, etc.
    return True, "PRODUCTION"


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _format_memory(lead_memory: dict) -> str:
    """Format lead memory dict into a string for system prompts."""
    if not lead_memory:
        return "No prior lead context available."
    lines = ["## LEAD CONTEXT"]
    for key, value in lead_memory.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _extract_state_block(state_prompts_text: str, state: str) -> str:
    """Extract the prompt block for a specific state from state_prompts.md.

    Looks for a heading like ``## STATE: DISCOVERY`` and returns everything
    until the next ``## STATE:`` heading or the end of the file.
    """
    pattern = re.compile(
        rf"^## STATE: {re.escape(state)}\b(.*?)(?=^## STATE: |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(state_prompts_text)
    if match:
        return match.group(1).strip()
    return f"[No prompt template found for state: {state}]"


def build_system_prompt(state: str, lead_memory: dict) -> str:
    """Compose the full system prompt for an LLM call.

    Combines persona, language policy, compliance, state-specific prompts,
    battle card, and lead memory into a single string.
    """
    demo_banner = "[DEMO MODE — fabricated context, test calls only]\n\n" if DEMO_MODE else ""
    return f"""{demo_banner}{PERSONA}

{LANGUAGE_POLICY_INSTRUCTION}

{COMPLIANCE}

CURRENT STATE: {state}
{_extract_state_block(STATE_PROMPTS, state)}

RELEVANT BATTLE CARD:
{BATTLE_CARD}

{_format_memory(lead_memory)}
"""


def build_objection_prompt(objection_text: str, lead_memory: dict) -> str:
    """Compose a system prompt specifically for objection handling."""
    return f"""{PERSONA}

{LANGUAGE_POLICY_INSTRUCTION}

OBJECTION HANDLING TASK:
The lead just said: "{objection_text}"

Respond using the Acknowledge → Reframe → Bridge → Re-engage pattern from:
{OBJECTIONS}

LEAD CONTEXT:
{_format_memory(lead_memory)}
"""


# ---------------------------------------------------------------------------
# Output validators
# ---------------------------------------------------------------------------

def validate_response_english_only(response: str) -> tuple[bool, str]:
    """Reject responses containing non-Latin scripts."""
    if NON_ENGLISH_SCRIPT_PATTERN.search(response):
        return False, "non_latin_script_detected"
    return True, ""


def validate_response_no_banned_phrases(response: str) -> tuple[bool, str]:
    """Reject responses containing banned phrases from banned_phrases.json."""
    lower = response.lower()
    hits = [p for p in BANNED_FLAT if p.lower() in lower]
    if hits:
        return False, f"banned_phrases: {hits}"
    return True, ""


def validate_response(response: str) -> tuple[bool, list[str]]:
    """Run all validators against an LLM response.

    Returns:
        (is_valid, list_of_failure_messages)
    """
    failures = []
    ok1, msg1 = validate_response_english_only(response)
    if not ok1:
        failures.append(msg1)
    ok2, msg2 = validate_response_no_banned_phrases(response)
    if not ok2:
        failures.append(msg2)
    return (len(failures) == 0, failures)


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

def startup_banner() -> None:
    """Print a startup banner showing mode and configuration."""
    mode = "DEMO" if DEMO_MODE else "PRODUCTION"
    print(
        f"""
╔══════════════════════════════════════════════════╗
║  voice-agent-kimi  —  Mode: {mode:<20}║
║  Language policy: ENGLISH ONLY                   ║
║  Whitelist: {len(DEMO_WHITELIST_NUMBERS)} number(s)                          ║
╚══════════════════════════════════════════════════╝
"""
    )
