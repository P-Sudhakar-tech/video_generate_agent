import re
from typing import List

from pydantic import BaseModel

from .client import call_structured, get_client
from .config import Config
from .models import VideoPackage

LANGUAGE_NAMES = {"en": "English", "te": "Telugu"}

# Characters allowed in translated narration per language, beyond ASCII and
# common punctuation. The model occasionally emits a stray glyph from another
# Indic script (e.g. a Tibetan vowel sign inside a Telugu word).
_SCRIPT_RANGES = {"te": r"\u0c00-\u0c7f"}


def _clean(text: str, language: str) -> str:
    extra = _SCRIPT_RANGES.get(language, "")
    return re.sub(rf"[^\x00-\x7f\u2000-\u206f{extra}]", "", text)


class TranslatedLine(BaseModel):
    scene_number: int
    text: str


class TranslationOutput(BaseModel):
    topic: str
    lines: List[TranslatedLine]


_SYSTEM = """You translate narration for a programming tutorial YouTube video into {language}.
Write natural, spoken {language} the way popular {language} coding YouTubers talk - friendly,
simple, conversational - not formal or literary. Write it in {language}'s native script
(for Telugu: తెలుగు లిపి), never romanized/transliterated into Latin letters. Keep
programming terms that {language} speakers normally say in English (variable, string, integer, function, print, Python, etc.)
in English, written in Latin script. Never translate or alter code, identifiers, values,
or output shown in the narration. Return exactly one entry per scene, with that scene's
number and its full translated narration (keep any line breaks inside it in that one entry)."""


def translate_package(package: VideoPackage, language: str, config: Config) -> VideoPackage:
    """Return a copy of package with the topic and every storyboard voiceover line
    translated. Code examples are left untouched, so code slides stay identical."""
    scenes = package.storyboard.scenes
    numbered = "\n\n".join(
        f"[Scene {i}]\n{scene.voiceover_line}" for i, scene in enumerate(scenes, start=1)
    )
    user = (
        f"Video topic: {package.topic}\n\n"
        f"Translate the topic and the narration of these {len(scenes)} scenes:\n\n{numbered}"
    )

    result = call_structured(
        get_client(), config, _SYSTEM.format(language=LANGUAGE_NAMES[language]), user, TranslationOutput
    )
    by_number = {line.scene_number: line.text.strip() for line in result.lines}
    missing = [i for i in range(1, len(scenes) + 1) if not by_number.get(i)]
    if missing:
        raise RuntimeError(f"Translation is missing scene(s) {missing} - re-run to retry.")

    translated = package.model_copy(deep=True)
    translated.topic = result.topic
    for i, scene in enumerate(translated.storyboard.scenes, start=1):
        scene.voiceover_line = _clean(by_number[i], language)
    return translated
