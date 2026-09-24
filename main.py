import argparse
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent.client import check_connection
from agent.config import Config
from agent.pipeline import run_pipeline
from agent.render import render_markdown


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return text or "video"


def main():
    parser = argparse.ArgumentParser(description="Create a coding YouTube video package.")
    parser.add_argument("--topic", default=None, help="Video topic, e.g. 'Python Variables' (required unless --check)")
    parser.add_argument(
        "--level",
        default="Beginner",
        choices=["Beginner", "Intermediate", "Advanced"],
        help="Target audience level (default: Beginner)",
    )
    parser.add_argument("--duration", type=int, default=8, help="Target duration in minutes (default: 8)")
    parser.add_argument("--model", default=None, help="Override the Gemini model (default: from config/env)")
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Disable local execution of generated code examples during QA",
    )
    parser.add_argument("--output", default=None, help="Output markdown file path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify GEMINI_API_KEY and model connectivity with one minimal call, then exit",
    )
    args = parser.parse_args()

    config = Config()
    if args.model:
        config.model = args.model
    if args.no_execute:
        config.execute_code = False

    if args.check:
        print(f"Checking connectivity to model '{config.model}'...")
        try:
            reply = check_connection(config)
        except Exception as exc:
            print(f"Check failed: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"OK - model responded: {reply!r}")
        return

    if not args.topic:
        parser.error("--topic is required (unless using --check)")

    print(f"Create Video\nTopic: {args.topic}\nLevel: {args.level}\nDuration: {args.duration} minutes\n")

    try:
        package = run_pipeline(args.topic, args.level, args.duration, config)
    except Exception as exc:  # surface API/config errors clearly instead of a raw traceback
        print(f"\nPipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)

    markdown = render_markdown(package)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else output_dir / f"{slugify(args.topic)}.md"
    output_path.write_text(markdown, encoding="utf-8")

    json_path = output_path.with_suffix(".json")
    json_path.write_text(package.model_dump_json(indent=2), encoding="utf-8")

    print(f"\nDone. Video package written to:\n  {output_path}\n  {json_path}")


if __name__ == "__main__":
    main()
