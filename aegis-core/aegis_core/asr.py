"""Speech -> text for aegis-core.

Model choice (see docs/ML_DESIGN.md section 1):
  * default: faster-whisper `large-v3-turbo` (multilingual, handles
    Hindi/English code-mixing acceptably, ~real-time on one GPU, int8 on CPU
    for short chunks);
  * Indic-heavy calls: swap in an AI4Bharat IndicConformer / IndicWhisper
    checkpoint behind the same `transcribe_chunk` interface.

This module only turns an audio chunk into text turns. Chunking, VAD-based
endpointing and the live stream belong to aegis-realtime, which calls
`transcribe_chunk` and feeds the resulting turns into `AegisSession.feed`.
Audio never leaves the device; only redacted text continues downstream.
"""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel  # optional dependency: pip install -e ".[asr]"

    name = os.getenv("AEGIS_ASR_MODEL", "large-v3-turbo")
    device = os.getenv("AEGIS_ASR_DEVICE", "auto")
    compute = os.getenv("AEGIS_ASR_COMPUTE", "int8_float16" if device != "cpu" else "int8")
    return WhisperModel(name, device=device, compute_type=compute)


def transcribe_chunk(audio, language: str | None = None, speaker: str = "caller", offset_ms: int = 0) -> list[dict]:
    """`audio`: file path or 16 kHz mono float32 numpy array.
    Returns turns shaped for AegisSession.feed: {speaker, text, at}."""
    segments, _info = _model().transcribe(
        audio, language=language, vad_filter=True, beam_size=1,
        condition_on_previous_text=False,
    )
    return [{"speaker": speaker, "text": s.text.strip(), "at": offset_ms + int(s.start * 1000)}
            for s in segments if s.text.strip()]
