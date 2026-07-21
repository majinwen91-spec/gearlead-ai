from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from gearlead.config import Settings, get_settings


class LLMError(RuntimeError):
    """Raised when the optional OpenAI-compatible API cannot complete a request."""


@dataclass
class LLMClient:
    settings: Settings

    @classmethod
    def from_settings(cls) -> "LLMClient":
        return cls(get_settings())

    @property
    def available(self) -> bool:
        return self.settings.llm_available

    def chat(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        if not self.available:
            raise LLMError("LLM is disabled. Set DEMO_MODE=false and configure OPENAI_API_KEY.")
        payload: dict[str, Any] = {
            "model": self.settings.openai_model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            f"{self.settings.openai_base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM response did not contain message content.") from exc

