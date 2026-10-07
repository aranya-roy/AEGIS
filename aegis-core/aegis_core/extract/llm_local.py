"""Local / self-hosted LLM extractor over an OpenAI-compatible HTTP endpoint.

Works with vLLM (`vllm serve Qwen/Qwen2.5-7B-Instruct`), Ollama
(`http://localhost:11434/v1`), llama.cpp server, or any LoRA-merged
fine-tune served the same way. JSON is constrained with `response_format`
(json_schema) where supported; output is always re-validated and grounded.
"""

from __future__ import annotations

import json
import os
import time

import httpx
from pydantic import ValidationError

from ..schema import LLMSemanticEvent, SemanticEvent
from .grounding import ground
from .prompts import chat_messages
from .schema_util import strict_schema


class LocalLLMExtractor:
    name = "llm"

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 timeout_s: float | None = None, api_key: str | None = None, constrained: bool = True,
                 few_shot: bool | None = None):
        self.base_url = (base_url or os.getenv("AEGIS_LLM_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
        self.model = model or os.getenv("AEGIS_LLM_MODEL", "qwen2.5:7b-instruct")
        self.timeout_s = timeout_s if timeout_s is not None else float(os.getenv("AEGIS_LLM_TIMEOUT_S", "3"))
        self.constrained = constrained
        self.few_shot = few_shot if few_shot is not None else os.getenv("AEGIS_LLM_FEWSHOT", "1") != "0"
        key = api_key or os.getenv("AEGIS_LLM_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = httpx.Client(timeout=self.timeout_s, headers=headers)
        self._schema = strict_schema(LLMSemanticEvent)
        self.last_latency_ms = 0.0
        self.last_error: str | None = None

    def raw(self, text: str, speaker: str = "caller", context: list[str] | None = None) -> str:
        body: dict = {
            "model": self.model,
            "messages": chat_messages(text, speaker, context, self.few_shot),
            "temperature": 0.0,
            "max_tokens": 600,
        }
        if self.constrained:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "semantic_event", "schema": self._schema, "strict": True},
            }
        r = self._client.post(f"{self.base_url}/chat/completions", json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def extract(self, text: str, speaker: str = "caller", turn_index: int = 0,
                context: list[str] | None = None) -> SemanticEvent | None:
        t0 = time.perf_counter()
        self.last_error = None
        try:
            content = self.raw(text, speaker, context)
            parsed = LLMSemanticEvent.model_validate(json.loads(_strip_fences(content)))
        except (httpx.HTTPError, json.JSONDecodeError, ValidationError, KeyError) as e:
            self.last_error = f"{type(e).__name__}: {e}"[:300]
            return None
        finally:
            self.last_latency_ms = (time.perf_counter() - t0) * 1000
        event = SemanticEvent(turn_index=turn_index, speaker=speaker, source="llm",  # type: ignore[arg-type]
                              **parsed.model_dump())
        grounded, _ = ground(event, text)
        return grounded


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        s = s.rsplit("```", 1)[0]
    return s.strip()
