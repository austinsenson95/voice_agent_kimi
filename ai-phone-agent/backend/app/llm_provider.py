"""
LLM Provider Abstraction Layer

This is the MOST IMPORTANT module in the entire backend. It defines a uniform
interface for all LLM providers so that switching between Groq, OpenAI,
Anthropic, and DeepSeek is a single env-var change with zero code changes
in the rest of the application.

Architecture:
    LLMProvider (ABC)
    ├── GroqProvider      → fast, <100ms TTFT, good for voice
    ├── OpenAIProvider    → reliable, best-in-class reasoning
    ├── AnthropicProvider → long context, excellent instruction following
    └── DeepSeekProvider  → cheapest option, good for high-volume

Usage:
    provider = get_llm_provider()  # reads LLM_PROVIDER env var
    response = await provider.generate(
        messages=[{"role": "user", "content": "Hello"}],
        system="You are a sales assistant...",
    )
    print(response.text)  # same interface for ALL providers
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.schemas import LLMResponse


# ---------------------------------------------------------------------------
# Abstract Base Class
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Uniform interface for all LLM providers.

    Every provider implements this interface so the rest of the app
    (webhooks, state machine, testing) never needs to know WHICH
    provider is running underneath.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'groq', 'openai'."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier currently in use, e.g. 'llama-3.3-70b-versatile'."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Generate a text completion from the LLM.

        Args:
            messages: Conversation history as [{"role": "user|assistant", "content": "..."}]
            system: System prompt/instructions (if supported by provider)
            tools: Optional function-calling tool definitions

        Returns:
            LLMResponse with standardized fields regardless of provider
        """
        ...

    def _calc_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate approximate cost in USD.

        Override in subclass if provider has special pricing.
        These rates are per 1M tokens and should be kept updated.
        """
        rates = {
            # Groq — extremely cheap, great for voice (rates as of early 2025)
            "llama-3.3-70b-versatile": (0.59, 0.79),
            "llama-3.1-8b-instant": (0.05, 0.08),
            "mixtral-8x7b-32768": (0.24, 0.24),
            # OpenAI
            "gpt-4.1-mini": (1.00, 3.00),
            "gpt-4.1": (5.00, 15.00),
            "gpt-4.1-nano": (0.10, 0.40),
            "gpt-3.5-turbo": (0.50, 1.50),
            # Anthropic
            "claude-sonnet-4-20250514": (3.00, 15.00),
            "claude-sonnet-4-1-20250514": (3.00, 15.00),
            "claude-haiku-4-20250514": (0.50, 1.50),
            # DeepSeek — cheapest
            "deepseek-v4-flash": (0.07, 0.27),
            "deepseek-v4": (0.50, 2.00),
        }
        prompt_rate, completion_rate = rates.get(self.model, (1.0, 3.0))
        return (
            prompt_tokens * prompt_rate + completion_tokens * completion_rate
        ) / 1_000_000


# ---------------------------------------------------------------------------
# Groq Provider — DEFAULT, fast TTFT for voice
# ---------------------------------------------------------------------------

class GroqProvider(LLMProvider):
    """Groq provider using OpenAI-compatible API.

    Groq runs on custom LPU hardware delivering <100ms time-to-first-token,
    making it ideal for real-time voice conversations where latency matters.

    API docs: https://console.groq.com/docs/openai
    """

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.provider_config("groq")
        self._api_key = cfg["api_key"]
        self._model = cfg["model"]
        self._temperature = cfg["temperature"]
        self._max_tokens = cfg["max_tokens"]
        self._base_url = cfg["base_url"]
        self._timeout = cfg["timeout_seconds"]

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Send chat completion request to Groq API."""
        if not self._api_key:
            return LLMResponse(
                text="Sorry, I'm not configured properly. Please contact support.",
                provider=self.name,
                model=self.model,
                error="GROQ_API_KEY not set",
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Groq uses OpenAI-compatible message format
        api_messages: List[Dict[str, str]] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="I'm having trouble connecting. Let me try again.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="I'm taking too long to respond. Let me try a shorter answer.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error="Request timed out",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Something went wrong on my end. Please bear with me.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=str(exc)[:500],
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Parse OpenAI-compatible response
        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            # Handle tool calls — for now just return the tool call info
            message = choice.get("message", {})
            if message.get("tool_calls"):
                text = f"[TOOL_CALL] {message['tool_calls'][0]['function']['name']}"
            else:
                text = message.get("content", "")

            return LLMResponse(
                text=text,
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                tokens_used=prompt_tokens + completion_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=self._calc_cost(prompt_tokens, completion_tokens),
                finish_reason=choice.get("finish_reason"),
            )
        except (KeyError, IndexError) as exc:
            return LLMResponse(
                text="I received an unexpected response. Let me try again.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"Malformed response: {str(exc)[:200]}",
            )


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
    """OpenAI provider using the standard Chat Completions API.

    Best for: high-quality reasoning, complex instruction following,
    and when you need the most reliable responses.
    """

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.provider_config("openai")
        self._api_key = cfg["api_key"]
        self._model = cfg["model"]
        self._temperature = cfg["temperature"]
        self._max_tokens = cfg["max_tokens"]
        self._base_url = cfg["base_url"]
        self._timeout = cfg["timeout_seconds"]

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        if not self._api_key:
            return LLMResponse(
                text="OpenAI is not configured. Please set OPENAI_API_KEY.",
                provider=self.name,
                model=self.model,
                error="OPENAI_API_KEY not set",
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        api_messages: List[Dict[str, str]] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Service temporarily unavailable. Please try again.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Request timed out. Let me give a shorter response.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error="Request timed out",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="An error occurred. Please try again.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=str(exc)[:500],
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            message = choice.get("message", {})
            text = message.get("content", "")

            return LLMResponse(
                text=text,
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                tokens_used=prompt_tokens + completion_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=self._calc_cost(prompt_tokens, completion_tokens),
                finish_reason=choice.get("finish_reason"),
            )
        except (KeyError, IndexError) as exc:
            return LLMResponse(
                text="Unexpected response format.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"Malformed response: {str(exc)[:200]}",
            )


# ---------------------------------------------------------------------------
# Anthropic Provider
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider using the Messages API.

    Claude excels at following complex instructions, maintaining context
    over long conversations, and producing natural-sounding dialogue.
    Best for: nuanced sales conversations, objection handling.

    API docs: https://docs.anthropic.com/en/api/messages
    """

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.provider_config("anthropic")
        self._api_key = cfg["api_key"]
        self._model = cfg["model"]
        self._temperature = cfg["temperature"]
        self._max_tokens = cfg["max_tokens"]
        self._base_url = cfg["base_url"]
        self._timeout = cfg["timeout_seconds"]

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        if not self._api_key:
            return LLMResponse(
                text="Anthropic is not configured. Please set ANTHROPIC_API_KEY.",
                provider=self.name,
                model=self.model,
                error="ANTHROPIC_API_KEY not set",
            )

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Anthropic uses a different message format — convert from OpenAI-style
        anthropic_messages = []
        for msg in messages:
            # Anthropic only supports 'user' and 'assistant' roles
            role = msg["role"]
            if role not in ("user", "assistant"):
                role = "user"
            anthropic_messages.append({
                "role": role,
                "content": msg["content"],
            })

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": anthropic_messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }
        if system:
            # Anthropic puts system prompt at top level, not in messages
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/messages",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Service temporarily unavailable.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Request timed out.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error="Request timed out",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="An error occurred.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=str(exc)[:500],
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        try:
            # Anthropic response format is different from OpenAI
            content_blocks = data.get("content", [])
            text_parts = []
            for block in content_blocks:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            text = " ".join(text_parts)

            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            return LLMResponse(
                text=text,
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                tokens_used=input_tokens + output_tokens,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                cost_usd=self._calc_cost(input_tokens, output_tokens),
                finish_reason=data.get("stop_reason"),
            )
        except (KeyError, IndexError) as exc:
            return LLMResponse(
                text="Unexpected response format from Anthropic.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"Malformed response: {str(exc)[:200]}",
            )


# ---------------------------------------------------------------------------
# DeepSeek Provider
# ---------------------------------------------------------------------------

class XAIProvider(LLMProvider):
    """xAI Grok provider using OpenAI-compatible API.

    Grok offers fast inference with strong instruction following.
    Uses the same message format as OpenAI.
    """

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.provider_config("xai")
        self._api_key = cfg["api_key"]
        self._model = cfg["model"]
        self._temperature = cfg["temperature"]
        self._max_tokens = cfg["max_tokens"]
        self._base_url = cfg["base_url"]
        self._timeout = cfg["timeout_seconds"]

    @property
    def name(self) -> str:
        return "xai"

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        if not self._api_key:
            return LLMResponse(
                text="xAI is not configured. Please set XAI_API_KEY.",
                provider=self.name,
                model=self.model,
                error="XAI_API_KEY not set",
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        api_messages: List[Dict[str, str]] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Service temporarily unavailable.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Request timed out.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error="Request timed out",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="An error occurred.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=str(exc)[:500],
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            message = choice.get("message", {})
            text = message.get("content", "")

            return LLMResponse(
                text=text,
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                tokens_used=prompt_tokens + completion_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=self._calc_cost(prompt_tokens, completion_tokens),
                finish_reason=choice.get("finish_reason"),
            )
        except (KeyError, IndexError) as exc:
            return LLMResponse(
                text="Unexpected response format.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"Malformed response: {str(exc)[:200]}",
            )


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider using OpenAI-compatible API.

    DeepSeek offers the cheapest inference costs while maintaining
    competitive quality. Ideal for high-volume operations or cost-sensitive
    deployments. Their V4-Flash model is optimized for speed.

    API docs: https://api-docs.deepseek.com/
    """

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.provider_config("deepseek")
        self._api_key = cfg["api_key"]
        self._model = cfg["model"]
        self._temperature = cfg["temperature"]
        self._max_tokens = cfg["max_tokens"]
        self._base_url = cfg["base_url"]
        self._timeout = cfg["timeout_seconds"]

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        if not self._api_key:
            return LLMResponse(
                text="DeepSeek is not configured. Please set DEEPSEEK_API_KEY.",
                provider=self.name,
                model=self.model,
                error="DEEPSEEK_API_KEY not set",
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        api_messages: List[Dict[str, str]] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Service temporarily unavailable.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="Request timed out.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error="Request timed out",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return LLMResponse(
                text="An error occurred.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=str(exc)[:500],
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            message = choice.get("message", {})
            text = message.get("content", "")

            return LLMResponse(
                text=text,
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                tokens_used=prompt_tokens + completion_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=self._calc_cost(prompt_tokens, completion_tokens),
                finish_reason=choice.get("finish_reason"),
            )
        except (KeyError, IndexError) as exc:
            return LLMResponse(
                text="Unexpected response format from DeepSeek.",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                error=f"Malformed response: {str(exc)[:200]}",
            )


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------

# Module-level cache for the current provider instance.
# This avoids recreating the provider (and re-reading env vars) on every request.
_provider_instance: Optional[LLMProvider] = None


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """Factory function: return a configured LLMProvider instance.

    Reads the LLM_PROVIDER env var (or uses the passed provider_name) to
    decide which provider class to instantiate. The result is cached so
    subsequent calls return the same instance.

    Args:
        provider_name: Override the env var. One of: 'groq', 'openai',
                       'anthropic', 'deepseek'. If None, reads LLM_PROVIDER.

    Returns:
        An LLMProvider instance ready to call generate().

    Example:
        provider = get_llm_provider()           # uses env var
        provider = get_llm_provider("openai")   # force OpenAI
    """
    global _provider_instance

    if provider_name is None:
        provider_name = get_settings().LLM_PROVIDER

    provider_name = provider_name.lower()

    # Re-instantiate only if the provider has changed
    if _provider_instance is not None and _provider_instance.name == provider_name:
        return _provider_instance

    providers = {
        "groq": GroqProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "deepseek": DeepSeekProvider,
        "xai": XAIProvider,
    }

    provider_class = providers.get(provider_name, XAIProvider)
    _provider_instance = provider_class()
    return _provider_instance


def reset_provider() -> None:
    """Clear the cached provider instance.

    Call this after changing settings at runtime so the next
    get_llm_provider() call creates a fresh instance.
    """
    global _provider_instance
    _provider_instance = None
