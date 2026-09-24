import json
import re
from pathlib import Path

from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

from .branding import intro_labels, intro_narration
from .config import Config
from .models import VideoPackage
from .tts import synthesize_speech, voice_id
from .visuals import add_caption, render_code_slide, render_cta_slide, render_title_slide

# Every scene is a still image, so a low frame rate looks identical and encodes
# far faster than 24fps (a 9-minute video took ~36 minutes at 24fps).
FPS = 8


def timings_path(output_path: str) -> Path:
    """Where build_video records each scene's start time, e.g. topic.te.timings.json."""
    return Path(output_path).with_suffix(".timings.json")


def build_video(
    package: VideoPackage, config: Config, output_path: str, work_dir: str, channel: str, log=print
) -> str:
    """Render a like/share/subscribe intro for channel, then every storyboard scene,
    as narrated clips (TTS audio + slide), concatenated into a single MP4. Also
    writes the actual start time of each scene to timings_path(output_path), which
    the YouTube kit uses for accurate chapter timestamps."""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    def voiceover(name: str, text: str, label: str) -> str:
        # Voice is in the filename so switching voice/language never mixes two voices.
        audio_path = work / f"{name}_{voice_id(config)}.wav"
        # Reuse audio from a previous run - the free-tier Gemini TTS quota is only
        # 10 requests/day, so a long video may be rendered across several runs.
        if audio_path.exists() and audio_path.stat().st_size > 0:
            log(f"  {label}: reusing existing voiceover")
        else:
            log(f"  {label}: synthesizing voiceover...")
            synthesize_speech(config, text, str(audio_path))
        return str(audio_path)

    code_by_title = {example.title: example for example in package.code.examples}
    scenes = package.storyboard.scenes
    total = len(scenes) + 1
    clips, timings, start = [], [], 0.0

    def add_clip(scene_number: int, frame, audio_path: str, text: str):
        nonlocal start
        frame_path = str(work / f"scene_{scene_number:02d}_{config.language}.png")
        frame.save(frame_path)
        audio_clip = AudioFileClip(audio_path)
        clips.append(ImageClip(frame_path).with_duration(audio_clip.duration).with_audio(audio_clip))
        timings.append({"scene": scene_number, "start": round(start, 2), "text": text})
        start += audio_clip.duration

    # Scene 0: channel intro. The channel name is in the cache key so renaming the
    # channel re-synthesizes it.
    channel_key = re.sub(r"[^a-z0-9]+", "-", channel.lower()).strip("-") or "channel"
    narration = intro_narration(channel, config.language)
    audio = voiceover(f"scene_00_intro-{channel_key}", narration, f"Scene 1/{total} (intro)")
    add_clip(0, render_cta_slide(channel, package.topic, intro_labels(config.language)), audio, narration)

    for i, scene in enumerate(scenes, start=1):
        label = f"Scene {i + 1}/{total}"
        audio = voiceover(f"scene_{i:02d}", scene.voiceover_line, label)
        log(f"  {label}: rendering visual...")
        example = code_by_title.get(scene.code_ref)
        if example:
            frame = add_caption(render_code_slide(example.code, example.language), scene.voiceover_line)
        else:
            frame = render_title_slide(scene.voiceover_line, package.topic)
        add_clip(i, frame, audio, scene.voiceover_line)

    log("Concatenating scenes...")
    # Every frame is the same 1920x1080 size, so "chain" is safe and skips the
    # per-frame compositing that "compose" does.
    final = concatenate_videoclips(clips, method="chain")

    log(f"Writing {output_path} ...")
    final.write_videofile(output_path, fps=FPS, codec="libx264", audio_codec="aac", logger=None)

    final.close()
    for clip in clips:
        clip.close()

    timings_path(output_path).write_text(
        json.dumps({"channel": channel, "duration": round(start, 2), "scenes": timings}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
