"""Claude extractor: async deep-analysis tier and teacher labeler.

Not on the real-time path (network round-trip, cost). Used for:
  * re-analysing a finished/ongoing conversation in the background,
  * labeling public / synthetic transcripts to build the SFT set that the
    local real-time model is fine-tuned on (distillation).

Only sanitized text is ever sent. Output is constrained with structured
outputs, then grounded like every other extractor.
"""

from __future__ import annotations

import json
import os
import time

import anthropic

from ..schema import LLMSemanticEvent, SemanticEvent
from .grounding import ground
from .prompts import FEW_SHOT, SYSTEM_PROMPT, render_user_message
from .schema_util import strict_schema


class ClaudeExtractor:
    name = "llm"

    def __init__(self, model: str | None = None, effort: str | None = None):
        self.client = anthropic.Anthropic()
        self.model = model or os.getenv("AEGIS_CLAUDE_MODEL", "claude-opus-5-5")
        self.effort = effort or os.getenv("AEGIS_CLAUDE_EFFORT", "low")
        self._schema = strict_schema(LLMSemanticEvent)
        self._shots: list[dict] = []
        for utt, out in FEW_SHOT:
            spk, body = utt[1:].split("] ", 1)
            self._shots.append({"role": "user", "content": render_user_message(body, spk)})
            self._shots.append({"role": "assistant", "content": json.dumps(out, ensure_ascii=False)})
        self.last_latency_ms = 0.0
        self.last_error: str | None = None

    def extract(self, text: str, speaker: str = "caller", turn_index: int = 0,
                context: list[str] | None = None) -> SemanticEvent | None:
        t0 = time.perf_counter()
        self.last_error = None
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[*self._shots, {"role": "user", "content": render_user_message(text, speaker, context)}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": self._schema},
                },
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            self.last_error = f"rate_limited: {e}"
            return None
        except anthropic.APIStatusError as e:
            self.last_error = f"api_error {e.status_code}: {e.message}"
            return None
        except anthropic.APIConnectionError as e:
            self.last_error = f"connection: {e}"
            return None
        finally:
            self.last_latency_ms = (time.perf_counter() - t0) * 1000

        if response.stop_reason == "refusal":
            self.last_error = "refusal"
            return None
        body = next((b.text for b in response.content if b.type == "text"), None)
        if body is None:
            self.last_error = f"no text block (stop_reason={response.stop_reason})"
            return None
        parsed = LLMSemanticEvent.model_validate(json.loads(body))
        event = SemanticEvent(turn_index=turn_index, speaker=speaker, source="llm",  # type: ignore[arg-type]
                              **parsed.model_dump())
        grounded, _ = ground(event, text)
        return grounded
