import os
from dataclasses import dataclass


@dataclass
class Config:
    # gemini-3.6-flash (the new-account default) was repeatedly overloaded (503) in
    # testing; gemini-flash-lite-latest was reliable, so it's the default here.
    model: str = os.environ.get("VIDEO_AGENT_MODEL", "gemini-flash-lite-latest")
    # gemini-3.1-flash-tts-preview hung in testing via the Interactions API - likely
    # the same silent-hang-on-exhausted-quota seen later with this model, so it may
    # be worth retesting now that tts.py uses generate_content.
    tts_model: str = os.environ.get("VIDEO_AGENT_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    tts_voice: str = os.environ.get("VIDEO_AGENT_TTS_VOICE", "Kore")
    # "edge" (Microsoft Edge neural voices via edge-tts - free, no key, no daily
    # quota, and has Indian English/Telugu voices) or "gemini" (10 requests/day free).
    tts_engine: str = os.environ.get("VIDEO_AGENT_TTS_ENGINE", "edge")
    # Narration language: "en" or "te". Empty edge_voice means pick the Indian male
    # voice for that language (see tts.EDGE_VOICES).
    language: str = "en"
    edge_voice: str = os.environ.get("VIDEO_AGENT_EDGE_VOICE", "")
    execute_code: bool = os.environ.get("VIDEO_AGENT_EXECUTE_CODE", "1") != "0"
    output_dir: str = os.environ.get("VIDEO_AGENT_OUTPUT_DIR", "outputs")
    max_tokens: int = int(os.environ.get("VIDEO_AGENT_MAX_TOKENS", "16000"))
    code_timeout_sec: int = int(os.environ.get("VIDEO_AGENT_CODE_TIMEOUT", "10"))
    max_retries: int = int(os.environ.get("VIDEO_AGENT_MAX_RETRIES", "3"))
    # Hard per-call timeout: the SDK's own http_options timeout does not reliably
    # bound client.interactions.create() calls (observed hangs past 60s), so
    # with_retry enforces this itself via a daemon thread.
    call_timeout_sec: int = int(os.environ.get("VIDEO_AGENT_CALL_TIMEOUT", "90"))
