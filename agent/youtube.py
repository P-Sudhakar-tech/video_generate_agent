"""YouTube upload kit: everything needed to publish a rendered video.

One Gemini text call writes the creative parts (titles, hook, tags, chapter
labels, thumbnail text, pinned comment...). Everything structural is assembled
here in code: chapter timestamps come from the rendered video's real scene
timings, and the description layout and call to action are fixed templates, so
they're always valid for YouTube.
"""
import json
from pathlib import Path
from typing import List

from pydantic import BaseModel

from .client import call_structured, get_client
from .config import Config
from .models import Chapter, VideoPackage
from .translate import LANGUAGE_NAMES


class ChapterBreak(BaseModel):
    scene_number: int
    label: str


class KitDraft(BaseModel):
    titles: List[str]
    hook: str
    learning_points: List[str]
    tags: List[str]
    hashtags: List[str]
    chapter_breaks: List[ChapterBreak]
    thumbnail_texts: List[str]
    thumbnail_concepts: List[str]
    pinned_comment: str
    playlist_name: str


class YouTubeKit(BaseModel):
    channel: str
    language: str
    video_file: str
    duration: str
    titles: List[str]
    description: str
    tags: List[str]
    tags_csv: str
    hashtags: List[str]
    chapters: List[Chapter]
    thumbnail_texts: List[str]
    thumbnail_concepts: List[str]
    pinned_comment: str
    playlist_name: str
    upload_settings: List[str]


_SYSTEM = """You are a YouTube growth expert for programming tutorial channels. You write
metadata that ranks in YouTube search and gets clicks without being clickbait: accurate,
specific, and beginner-friendly. All human-facing text must be written in {language}."""

_TELUGU_NOTES = """
This is a Telugu-language video. Write titles, hook, learning points, chapter labels,
thumbnail texts and the pinned comment in Telugu script, keeping programming terms in
English (as Telugu coding YouTubers do). Every title must contain the topic in English plus
"in Telugu" (e.g. "Python Variables in Telugu | ...") - that is how Telugu viewers search.
Tags: mix English tags and "<topic> in telugu" style tags."""

# Fixed description wording per language.
_DESCRIPTION_TEXT = {
    "en": {
        "learn": "📚 In this video you'll learn:",
        "chapters": "⏱️ Chapters",
        "cta": "👍 If this video helped you, please LIKE, SHARE it with a friend, and SUBSCRIBE to {channel} "
        "for more coding tutorials.\n🔔 Hit the bell icon so you never miss a new video!",
    },
    "te": {
        "learn": "📚 ఈ వీడియోలో మీరు నేర్చుకునేవి:",
        "chapters": "⏱️ Chapters",
        "cta": "👍 ఈ వీడియో మీకు ఉపయోగపడితే LIKE చేయండి, మీ friends తో SHARE చేయండి, మరిన్ని coding "
        "వీడియోల కోసం {channel} ని SUBSCRIBE చేయండి.\n🔔 కొత్త వీడియోలు మిస్ అవ్వకుండా bell icon నొక్కండి!",
    },
}

MIN_CHAPTER_SEC = 10  # YouTube ignores chapter lists with a chapter shorter than 10s


def kit_path(video_path: str) -> Path:
    return Path(video_path).with_suffix(".youtube.json")


def _timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _build_chapters(breaks: List[ChapterBreak], timings: dict, intro_label: str) -> List[Chapter]:
    """Turn the model's chapter breaks (by scene number) into timestamps that meet
    YouTube's rules: first chapter at 0:00, at least 3 chapters, each >= 10s."""
    starts = {s["scene"]: s["start"] for s in timings["scenes"]}
    duration = timings["duration"]

    chapters = [(0.0, intro_label)]
    for brk in sorted(breaks, key=lambda b: b.scene_number):
        start = starts.get(brk.scene_number)
        if start is None or start <= 0:
            continue
        if start - chapters[-1][0] < MIN_CHAPTER_SEC:
            continue
        chapters.append((start, brk.label.strip()))
    if duration - chapters[-1][0] < MIN_CHAPTER_SEC and len(chapters) > 1:
        chapters.pop()
    if len(chapters) < 3:
        return []  # YouTube needs >= 3 chapters; better none than a list it rejects
    return [Chapter(timestamp=_timestamp(start), label=label) for start, label in chapters]


def _clean_tags(tags: List[str]) -> List[str]:
    """Dedupe and fit YouTube's 500-character total tag limit."""
    result, seen, total = [], set(), 0
    for tag in tags:
        tag = tag.strip().lstrip("#").replace(",", " ").strip()
        if not tag or tag.lower() in seen:
            continue
        cost = len(tag) + (2 if " " in tag else 0) + (1 if result else 0)
        if total + cost > 480:
            break
        result.append(tag)
        seen.add(tag.lower())
        total += cost
    return result


def generate_kit(package: VideoPackage, language: str, channel: str, video_path: str, config: Config) -> YouTubeKit:
    """Generate the upload kit for a rendered video (needs its .timings.json) and
    save it next to the video as <video>.youtube.json and <video>.youtube.md."""
    from .video import timings_path

    timings = json.loads(timings_path(video_path).read_text(encoding="utf-8"))
    lang_name = LANGUAGE_NAMES[language]

    scene_list = "\n".join(
        f"Scene {s['scene']} at {_timestamp(s['start'])}: {s['text'][:220]}" for s in timings["scenes"] if s["scene"] > 0
    )
    user = f"""Channel name: {channel}
Video topic: {package.topic}
Level: {package.level}
Video length: {_timestamp(timings['duration'])}
Learning objectives: {'; '.join(package.research.learning_objectives)}
Code examples shown: {'; '.join(e.title for e in package.code.examples)}

Scenes (scene 0 is the channel intro at 0:00, already a chapter):
{scene_list}
{_TELUGU_NOTES if language == 'te' else ''}
Produce:
- titles: 5 title options, each under 70 characters, topic keyword near the start
- hook: 2-3 sentence opening paragraph for the description (the first 150 characters show in search)
- learning_points: 4-6 short bullet points of what viewers will learn
- tags: 15-25 search tags, most specific first
- hashtags: 3-5 hashtags, each starting with #, no spaces
- chapter_breaks: 4-8 chapters as (scene_number, short label) where a new section starts; scene numbers >= 1
- thumbnail_texts: 3 options of 2-4 punchy words for the thumbnail
- thumbnail_concepts: 2 thumbnail layout ideas (what is shown, colors, expression)
- pinned_comment: a friendly first comment from {channel} asking a question to drive replies
- playlist_name: the playlist this video belongs in"""

    draft = call_structured(get_client(), config, _SYSTEM.format(language=lang_name), user, KitDraft)

    text = _DESCRIPTION_TEXT[language]
    chapters = _build_chapters(draft.chapter_breaks, timings, "Intro")
    hashtags = [h if h.startswith("#") else f"#{h}" for h in (h.strip().replace(" ", "") for h in draft.hashtags) if h][:5]

    parts = [draft.hook.strip(), text["learn"] + "\n" + "\n".join(f"✅ {p}" for p in draft.learning_points)]
    if chapters:
        parts.append(text["chapters"] + "\n" + "\n".join(f"{c.timestamp} {c.label}" for c in chapters))
    parts.append(text["cta"].format(channel=channel))
    parts.append(" ".join(hashtags))
    description = "\n\n".join(parts)

    tags = _clean_tags(draft.tags)
    kit = YouTubeKit(
        channel=channel,
        language=lang_name,
        video_file=Path(video_path).name,
        duration=_timestamp(timings["duration"]),
        titles=[t.strip() for t in draft.titles][:5],
        description=description,
        tags=tags,
        tags_csv=", ".join(tags),
        hashtags=hashtags,
        chapters=chapters,
        thumbnail_texts=draft.thumbnail_texts,
        thumbnail_concepts=draft.thumbnail_concepts,
        pinned_comment=draft.pinned_comment.strip(),
        playlist_name=draft.playlist_name.strip(),
        upload_settings=[
            "Category: Education",
            f"Video language: {lang_name}",
            "Audience: No, it's not made for kids",
            "Altered or synthetic content: Yes - the narration uses an AI (synthetic) voice",
            f"Playlist: {draft.playlist_name.strip()}",
            "Add an end screen (last 5-20s) with a Subscribe element and a related video",
            "Upload a custom thumbnail (1280x720) using one of the thumbnail texts",
        ],
    )

    out = kit_path(video_path)
    out.write_text(kit.model_dump_json(indent=2), encoding="utf-8")
    out.with_suffix(".md").write_text(render_kit_markdown(kit), encoding="utf-8")
    return kit


def render_kit_markdown(kit: YouTubeKit) -> str:
    def bullets(items):
        return "\n".join(f"- {i}" for i in items)

    return f"""# YouTube upload kit - {kit.video_file}

Channel: **{kit.channel}** · Language: {kit.language} · Length: {kit.duration}

## Title options
{bullets(kit.titles)}

## Description (paste as-is)
```
{kit.description}
```

## Tags (paste into the Tags box)
```
{kit.tags_csv}
```

## Hashtags
{' '.join(kit.hashtags)}

## Thumbnail text
{bullets(kit.thumbnail_texts)}

## Thumbnail ideas
{bullets(kit.thumbnail_concepts)}

## Pinned comment
```
{kit.pinned_comment}
```

## Upload settings checklist
{bullets(kit.upload_settings)}
"""
