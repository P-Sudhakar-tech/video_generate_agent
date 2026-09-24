import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent.config import Config
from agent.models import VideoPackage
from agent.translate import LANGUAGE_NAMES, translate_package
from agent.tts import TTS_ENGINES, voice_id
from agent.video import build_video
from agent.youtube import generate_kit


def load_localized_package(package_path: Path, package: VideoPackage, language: str, config: Config) -> VideoPackage:
    """English is the package as generated; other languages are translated once
    and cached next to it as <topic>.<lang>.json (edit that file to fix wording)."""
    if language == "en":
        return package
    cache_path = package_path.with_suffix(f".{language}.json")
    if cache_path.exists():
        print(f"Using existing translation: {cache_path}")
        return VideoPackage.model_validate_json(cache_path.read_text(encoding="utf-8"))
    print(f"Translating narration to {LANGUAGE_NAMES[language]}...")
    translated = translate_package(package, language, config)
    cache_path.write_text(translated.model_dump_json(indent=2), encoding="utf-8")
    print(f"Translation saved to: {cache_path}")
    return translated


def main():
    parser = argparse.ArgumentParser(description="Render an MP4 from a video package JSON file.")
    parser.add_argument("package", help="Path to a <topic>.json file produced by main.py")
    parser.add_argument(
        "--output",
        default=None,
        help="Output MP4 path (default: <topic>.mp4 for English, <topic>.<lang>.mp4 otherwise)",
    )
    parser.add_argument(
        "--channel",
        required=True,
        help="Your YouTube channel name, used in the like/share/subscribe intro and the YouTube kit",
    )
    parser.add_argument(
        "--no-kit",
        action="store_true",
        help="Skip generating the YouTube upload kit (titles, description, tags, chapters...)",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        choices=list(LANGUAGE_NAMES),
        default=["en"],
        help="Narration language(s), one video each, e.g. --lang en te (default: en)",
    )
    parser.add_argument(
        "--tts",
        choices=TTS_ENGINES,
        default=None,
        help="Voice engine: edge (free, Indian male voices, no daily limit) or gemini "
        "(10 requests/day free). Default: $VIDEO_AGENT_TTS_ENGINE or edge",
    )
    args = parser.parse_args()
    channel = args.channel.strip()
    if not channel:
        parser.error("--channel cannot be empty")
    if args.output and len(args.lang) > 1:
        parser.error("--output can only be used with a single --lang")

    package_path = Path(args.package)
    package = VideoPackage.model_validate_json(package_path.read_text(encoding="utf-8"))
    work_dir = package_path.parent / f"{package_path.stem}_scenes"

    for language in args.lang:
        config = Config()
        config.language = language
        if args.tts:
            config.tts_engine = args.tts

        if args.output:
            output_path = Path(args.output)
        elif language == "en":
            output_path = package_path.with_suffix(".mp4")
        else:
            output_path = package_path.with_suffix(f".{language}.mp4")

        try:
            localized = load_localized_package(package_path, package, language, config)
            print(
                f"\nBuilding {LANGUAGE_NAMES[language]} video for '{localized.topic}' "
                f"({len(localized.storyboard.scenes)} scenes, voice {voice_id(config)})..."
            )
            build_video(localized, config, str(output_path), str(work_dir), channel)
        except Exception as exc:
            print(f"\nVideo build failed: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Done. Video written to: {output_path}")

        if not args.no_kit:
            print("Generating YouTube upload kit...")
            try:
                generate_kit(localized, language, channel, str(output_path), config)
            except Exception as exc:
                # The video is fine; the kit can be regenerated from the UI's Library tab.
                print(f"YouTube kit failed (video is still OK): {exc}", file=sys.stderr)
                continue
            print(f"YouTube kit written to: {output_path.with_suffix('.youtube.md')}")


if __name__ == "__main__":
    main()
