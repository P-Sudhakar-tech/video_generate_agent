import asyncio
import os
import subprocess
import wave

import imageio_ffmpeg
from google.genai import types

from .client import get_client, is_daily_quota_error, with_retry
from .config import Config

TTS_ENGINES = ("edge", "gemini")

# Indian male voices per narration language.
EDGE_VOICES = {"en": "en-IN-PrabhatNeural", "te": "te-IN-MohanNeural"}


class TTSQuotaExhausted(RuntimeError):
    """The Gemini free-tier daily TTS quota (10 requests/day/model) is used up."""


def voice_id(config: Config) -> str:
    """Short identifier for the voice that will be used, e.g. 'edge-te-IN-MohanNeural'."""
    if config.tts_engine == "gemini":
        return f"gemini-{config.tts_voice}"
    return f"edge-{config.edge_voice or EDGE_VOICES[config.language]}"


def synthesize_speech(config: Config, text: str, output_path: str) -> float:
    """Generate speech for text with the configured engine, write it to
    output_path as a WAV file, and return its duration in seconds."""
    if config.tts_engine == "gemini":
        return _synthesize_gemini(config, text, output_path)
    if config.tts_engine == "edge":
        return _synthesize_edge(config, text, output_path)
    raise ValueError(f"Unknown TTS engine {config.tts_engine!r} (expected one of {TTS_ENGINES})")


def _synthesize_gemini(config: Config, text: str, output_path: str) -> float:
    # Uses generate_content rather than the Interactions API: when the daily quota
    # is exhausted, interactions.create() hangs silently instead of returning a 429,
    # while generate_content fails immediately with a clear RESOURCE_EXHAUSTED.
    client = get_client()

    def _call():
        return client.models.generate_content(
            model=config.tts_model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=config.tts_voice)
                    )
                ),
            ),
        )

    try:
        response = with_retry(config, _call)
    except Exception as exc:
        if is_daily_quota_error(exc):
            raise TTSQuotaExhausted(
                f"Gemini TTS daily free-tier quota for {config.tts_model} is used up (10 requests/day, "
                "resets at midnight Pacific). Re-run later - finished scenes are reused - "
                "or render with --tts edge."
            ) from exc
        raise

    part = response.candidates[0].content.parts[0] if response.candidates else None
    if part is None or part.inline_data is None or not part.inline_data.data:
        raise RuntimeError(f"TTS returned no audio for text: {text[:80]!r}")

    # Raw 16-bit PCM, mono; rate is in the mime type (e.g. "audio/L16;codec=pcm;rate=24000").
    pcm = part.inline_data.data
    sample_rate = 24000
    for param in (part.inline_data.mime_type or "").split(";"):
        if param.strip().startswith("rate="):
            sample_rate = int(param.strip()[len("rate="):])

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)

    return len(pcm) / (sample_rate * 2)


def _synthesize_edge(config: Config, text: str, output_path: str) -> float:
    # Microsoft Edge's online neural voices via edge-tts: free, no API key, no
    # daily quota. It returns MP3, which is converted to WAV with the ffmpeg
    # binary bundled in imageio-ffmpeg so every engine produces the same format.
    import edge_tts

    mp3_path = output_path + ".mp3"
    voice = config.edge_voice or EDGE_VOICES[config.language]
    asyncio.run(edge_tts.Communicate(text, voice).save(mp3_path))

    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", mp3_path, output_path],
        check=True,
    )
    os.remove(mp3_path)

    with wave.open(output_path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()
