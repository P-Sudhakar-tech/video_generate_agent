import queue
import threading
import time

from google import genai
from google.genai import types

from .config import Config

# Substrings indicating a transient error worth retrying with backoff: free-tier
# rate limits (429/quota) and server-side overload (503/UNAVAILABLE), both of
# which are common on Gemini's free tier.
_RETRYABLE_MARKERS = (
    "429",
    "RESOURCE_EXHAUSTED",
    "rate limit",
    "quota",
    "503",
    "UNAVAILABLE",
    "overloaded",
    "timeout",
    "timed out",
)

# Bound every request - without this, a stalled connection on the free tier can
# hang indefinitely instead of raising something our retry logic can catch.
_REQUEST_TIMEOUT_MS = 60_000


def get_client() -> genai.Client:
    return genai.Client(http_options=types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS))


def _call_with_hard_timeout(fn, timeout_sec):
    """Run fn() on a daemon thread and enforce timeout_sec ourselves. Needed
    because the SDK's http_options timeout does not reliably bound
    client.interactions.create() calls (observed indefinite hangs in testing).
    A daemon thread means a permanently stuck call still won't block process exit."""
    result_queue = queue.Queue(maxsize=1)

    def _runner():
        try:
            result_queue.put(("ok", fn()))
        except Exception as exc:
            result_queue.put(("error", exc))

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    try:
        status, value = result_queue.get(timeout=timeout_sec)
    except queue.Empty:
        raise TimeoutError(f"Call timed out after {timeout_sec}s (no response)")
    if status == "error":
        raise value
    return value


def is_daily_quota_error(exc: Exception) -> bool:
    """A free-tier per-day quota 429 - retrying within seconds can't succeed."""
    return "PerDay" in str(exc)


def with_retry(config: Config, fn):
    last_exc = None
    for attempt in range(config.max_retries + 1):
        try:
            return _call_with_hard_timeout(fn, config.call_timeout_sec)
        except Exception as exc:
            last_exc = exc
            is_retryable = not is_daily_quota_error(exc) and any(
                marker.lower() in str(exc).lower() for marker in _RETRYABLE_MARKERS
            )
            if attempt < config.max_retries and is_retryable:
                delay = 5 * (2**attempt)
                time.sleep(delay)
                continue
            raise
    raise last_exc


def call_structured(client, config: Config, system: str, user: str, output_format, max_tokens=None):
    """Call Gemini and parse the response against a Pydantic model, retrying on
    transient errors (rate limits and server overload are common on the free tier)."""

    def _call():
        response = client.models.generate_content(
            model=config.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=output_format.model_json_schema(),
                max_output_tokens=max_tokens or config.max_tokens,
            ),
        )
        if not response.text:
            # Current Gemini models spend part of max_output_tokens on internal
            # "thinking" before the visible answer - a too-small budget truncates
            # to an empty response instead of an error.
            raise RuntimeError(
                f"Empty response from {config.model} (finish_reason="
                f"{response.candidates[0].finish_reason if response.candidates else '?'}). "
                "Likely truncated by max_output_tokens - increase VIDEO_AGENT_MAX_TOKENS."
            )
        return output_format.model_validate_json(response.text)

    return with_retry(config, _call)


def check_connection(config: Config) -> str:
    """Make one minimal call to verify the API key and model both work."""
    client = get_client()

    def _call():
        response = client.models.generate_content(
            model=config.model,
            # Budget covers this model's internal "thinking" tokens plus the reply -
            # a too-small max_output_tokens truncates to an empty response.text.
            config=types.GenerateContentConfig(max_output_tokens=500),
            contents="Reply with exactly one word: OK",
        )
        return response.text

    return with_retry(config, _call)
