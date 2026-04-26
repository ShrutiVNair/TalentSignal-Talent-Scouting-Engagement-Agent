from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

GEMINI_MODEL = "gemini-1.5-flash"
DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324:free"


@dataclass
class LLMResponse:
    """Normalized LLM response metadata used by the existing app."""

    text: str
    provider: str
    model: str


@dataclass
class LLMCallMeta:
    """Tracks the last provider/model used for a call."""

    provider: str = "Fallback"
    model: str = "rule-based"


class LLMClient:
    """Unified client with Gemini, OpenRouter, and safe fallback routing."""

    def __init__(self) -> None:
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.openrouter_model = os.getenv(
            "OPENROUTER_MODEL",
            DEFAULT_OPENROUTER_MODEL,
        ).strip()
        self.last_call_meta = LLMCallMeta()

    def routing_summary(self) -> str:
        """Return a recruiter-friendly summary of active model routing."""

        if self.gemini_api_key:
            return f"Gemini primary ({GEMINI_MODEL})"
        if self.openrouter_api_key:
            return f"OpenRouter fallback ({self.openrouter_model})"
        return "Offline deterministic fallback"

    def is_available(self) -> bool:
        """Return whether any network LLM provider is configured."""

        return bool(self.gemini_api_key or self.openrouter_api_key)

    def call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """Call the first available LLM provider and return plain text or safe fallback."""

        if self.gemini_api_key:
            text = self._request_with_retry(
                provider="Gemini",
                model=GEMINI_MODEL,
                request_fn=lambda: self._call_gemini(prompt, temperature),
            )
            if text:
                return text

        if self.openrouter_api_key:
            text = self._request_with_retry(
                provider="OpenRouter",
                model=self.openrouter_model,
                request_fn=lambda: self._call_openrouter(prompt, temperature),
            )
            if text:
                return text

        self.last_call_meta = LLMCallMeta(provider="Fallback", model="rule-based")
        return ""

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> LLMResponse | None:
        """Backwards-compatible structured completion wrapper for existing modules."""

        prompt = (
            f"System instructions:\n{system_prompt.strip()}\n\n"
            f"User input:\n{user_prompt.strip()}"
        )
        text = self.call_llm(prompt, temperature=temperature)
        if not text:
            return None
        return LLMResponse(
            text=text,
            provider=self.last_call_meta.provider,
            model=self.last_call_meta.model,
        )

    def _request_with_retry(
        self,
        provider: str,
        model: str,
        request_fn: Any,
        retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> str:
        """Retry transient LLM failures and fall back safely if all attempts fail."""

        for attempt in range(retries):
            try:
                text = request_fn()
            except tuple(_httpx_exceptions()):
                text = ""
            if text:
                self.last_call_meta = LLMCallMeta(provider=provider, model=model)
                return text
            if attempt < retries - 1:
                time.sleep(backoff_seconds * (attempt + 1))
        return ""

    def _call_gemini(self, prompt: str, temperature: float) -> str:
        """Call the Gemini API and return plain text."""

        if httpx is None:
            return ""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 700,
            },
        }
        with httpx.Client(timeout=18.0) as client:
            response = client.post(url, params={"key": self.gemini_api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
        return self._extract_gemini_text(data)

    def _call_openrouter(self, prompt: str, temperature: float) -> str:
        """Call the OpenRouter chat completions API and return plain text."""

        if httpx is None:
            return ""
        payload = {
            "model": self.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=18.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Malformed OpenRouter response") from exc

    @staticmethod
    def _extract_gemini_text(data: dict[str, Any]) -> str:
        """Extract plain text from a Gemini response."""

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Empty Gemini response")
        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        combined = "\n".join(text_parts).strip()
        if not combined:
            raise ValueError("Gemini response did not contain text")
        return combined


_DEFAULT_CLIENT: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return a shared module-level LLM client."""

    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = LLMClient()
    return _DEFAULT_CLIENT


def call_llm(prompt: str, temperature: float = 0.3) -> str:
    """Unified public function used by new agent modules."""

    return get_llm_client().call_llm(prompt=prompt, temperature=temperature)


def _httpx_exceptions() -> tuple[type[BaseException], ...]:
    if httpx is None:
        return (ValueError,)
    return (httpx.HTTPError, httpx.TimeoutException, ValueError)
