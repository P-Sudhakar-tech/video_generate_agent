"""Streamlit UI for the Coding YouTube Agent.

Run with:  .venv\\Scripts\\streamlit run app.py
"""
import json
import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.client import check_connection
from agent.config import Config
from agent.models import VideoPackage
from agent.pipeline import run_pipeline
from agent.render import render_markdown
from agent.translate import LANGUAGE_NAMES
from agent.tts import TTS_ENGINES, voice_id
from agent.video import build_video, timings_path
from agent.youtube import YouTubeKit, generate_kit, kit_path, render_kit_markdown
from main import slugify
from make_video import load_localized_package

st.set_page_config(page_title="Coding YouTube Agent", page_icon="🎬", layout="wide")

OUTPUT_DIR = Path(Config().output_dir)
LEVELS = ["Beginner", "Intermediate", "Advanced"]
_SCENE_PROGRESS = re.compile(r"Scene (\d+)/(\d+)")


def list_packages() -> list[Path]:
    """Base package JSONs (python-variables.json), not translations (python-variables.te.json)."""
    if not OUTPUT_DIR.is_dir():
        return []
    paths = [p for p in OUTPUT_DIR.glob("*.json") if "." not in p.stem]
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def video_path(package_path: Path, language: str) -> Path:
    return package_path.with_suffix(".mp4" if language == "en" else f".{language}.mp4")


def load_package(path: Path) -> VideoPackage:
    return VideoPackage.model_validate_json(path.read_text(encoding="utf-8"))


def show_kit(kit: YouTubeKit, key: str):
    """Everything needed to publish on YouTube, each block with a copy button."""
    st.markdown(f"**Title options** (pick one, max 100 chars)")
    for title in kit.titles:
        st.code(title, language=None)
    st.markdown("**Description** (paste as-is - chapters, call to action and hashtags included)")
    st.code(kit.description, language=None)
    st.markdown(f"**Tags** ({len(kit.tags_csv)}/500 characters)")
    st.code(kit.tags_csv, language=None)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Thumbnail text**")
        for text in kit.thumbnail_texts:
            st.code(text, language=None)
    with col2:
        st.markdown("**Thumbnail ideas**")
        for idea in kit.thumbnail_concepts:
            st.write(f"- {idea}")
    st.markdown("**Pinned comment**")
    st.code(kit.pinned_comment, language=None)
    st.markdown("**Upload settings checklist**")
    for item in kit.upload_settings:
        st.checkbox(item, key=f"{key}-{item}")
    st.download_button(
        "Download upload kit (.md)", render_kit_markdown(kit), file_name=kit_path(kit.video_file).with_suffix(".md").name,
        key=f"kit-md-{key}",
    )


def make_kit(package_path: Path, package: VideoPackage, language: str, video: Path, channel: str) -> YouTubeKit:
    config = Config()
    config.model = model
    config.language = language
    localized = load_localized_package(package_path, package, language, config)
    return generate_kit(localized, language, channel, str(video), config)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🎬 Coding YouTube Agent")
    st.caption("Topic → script, code, storyboard → narrated MP4 in English and Telugu.")

    if os.environ.get("GEMINI_API_KEY"):
        st.success("GEMINI_API_KEY is set")
    else:
        st.error("GEMINI_API_KEY is missing - add it to .env and restart.")

    channel = st.text_input(
        "Channel name *",
        placeholder="e.g. CodeForge",
        help="Required. Shown in the like/share/subscribe intro and used in the YouTube description.",
    ).strip()
    if not channel:
        st.warning("Enter your channel name to render videos.")

    model = st.text_input("Text model", value=Config().model, help="Used for script generation and translation.")
    if st.button("Check connection"):
        config = Config()
        config.model = model
        with st.spinner(f"Calling {model}..."):
            try:
                st.success(f"OK - model replied {check_connection(config)!r}")
            except Exception as exc:
                st.error(f"Check failed: {exc}")

    st.divider()
    st.caption(f"Outputs folder: `{OUTPUT_DIR.resolve()}`")

create_tab, video_tab, library_tab = st.tabs(["1 · Create package", "2 · Make video", "3 · Library"])

# ---------------------------------------------------------------- 1. create package
with create_tab:
    st.subheader("Generate a video production package")
    st.caption("Research, script, code examples (run locally for QA), storyboard and YouTube metadata - about 7 API calls.")

    with st.form("create"):
        topic = st.text_input("Topic", placeholder="e.g. Python Lists")
        col1, col2 = st.columns(2)
        level = col1.selectbox("Level", LEVELS)
        duration = col2.number_input("Target duration (minutes)", min_value=1, max_value=60, value=8)
        execute = st.checkbox(
            "Run generated code examples locally for QA",
            value=Config().execute_code,
            help="Executes LLM-generated code on this machine (with a timeout, no sandbox).",
        )
        submitted = st.form_submit_button("Generate package", type="primary")

    if submitted:
        if not topic.strip():
            st.warning("Enter a topic first.")
        else:
            config = Config()
            config.model = model
            config.execute_code = execute
            slug = slugify(topic)
            with st.status(f"Generating package for '{topic}'...", expanded=True) as status:
                try:
                    package = run_pipeline(topic.strip(), level, int(duration), config, log=st.write)
                except Exception as exc:
                    status.update(label="Package generation failed", state="error")
                    st.error(str(exc))
                    st.stop()
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                (OUTPUT_DIR / f"{slug}.md").write_text(render_markdown(package), encoding="utf-8")
                (OUTPUT_DIR / f"{slug}.json").write_text(package.model_dump_json(indent=2), encoding="utf-8")
                status.update(label=f"Package ready: {slug}.json", state="complete")

            st.success(f"Saved `{slug}.md` and `{slug}.json`. Go to **2 · Make video** to render it.")
            if package.final_qa.issues:
                with st.expander(f"Final QA flagged {len(package.final_qa.issues)} issue(s)"):
                    for issue in package.final_qa.issues:
                        st.write(f"- {issue}")

# ---------------------------------------------------------------- 2. make video
with video_tab:
    st.subheader("Render narrated videos")
    packages = list_packages()
    if not packages:
        st.info("No packages yet - create one in **1 · Create package**.")
    else:
        package_path = st.selectbox("Package", packages, format_func=lambda p: p.stem)
        package = load_package(package_path)
        st.caption(
            f"**{package.topic}** · {package.level} · {len(package.storyboard.scenes)} scenes · "
            f"{len(package.code.examples)} code examples"
        )

        col1, col2 = st.columns(2)
        languages = col1.multiselect(
            "Languages",
            list(LANGUAGE_NAMES),
            default=["en"],
            format_func=LANGUAGE_NAMES.get,
            help="One video per language. Telugu narration is translated once and cached.",
        )
        engine = col2.radio(
            "Voice engine",
            TTS_ENGINES,
            format_func={
                "edge": "Edge - Indian male voices, free, no daily limit",
                "gemini": "Gemini - 10 scenes/day on the free tier",
            }.get,
        )

        existing = [lang for lang in languages if video_path(package_path, lang).exists()]
        if existing:
            st.caption(
                "Already rendered: " + ", ".join(LANGUAGE_NAMES[lang] for lang in existing)
                + " - rendering again overwrites it (cached scene audio is reused)."
            )

        if not channel:
            st.info("Enter your **channel name** in the sidebar - every video opens with a like/share/subscribe intro for it.")
        if st.button("Render video", type="primary", disabled=not languages or not channel):
            work_dir = package_path.parent / f"{package_path.stem}_scenes"
            for language in languages:
                config = Config()
                config.model = model
                config.language = language
                config.tts_engine = engine
                out = video_path(package_path, language)
                name = LANGUAGE_NAMES[language]

                with st.status(f"{name} video ({voice_id(config)})...", expanded=True) as status:
                    progress = st.progress(0.0, text="Starting...")

                    def log(message: str, progress=progress):
                        match = _SCENE_PROGRESS.search(message)
                        if match:
                            done, total = int(match.group(1)), int(match.group(2))
                            progress.progress((done - 1) / total, text=message.strip())
                        else:
                            progress.progress(1.0, text=message.strip())
                            st.write(message.strip())

                    try:
                        localized = load_localized_package(package_path, package, language, config)
                        build_video(localized, config, str(out), str(work_dir), channel, log=log)
                    except Exception as exc:
                        status.update(label=f"{name} video failed", state="error")
                        st.error(str(exc))
                        continue
                    st.write("Writing YouTube upload kit (titles, description, tags, chapters)...")
                    try:
                        kit = generate_kit(localized, language, channel, str(out), config)
                    except Exception as exc:
                        kit = None
                        st.warning(f"Video is ready, but the YouTube kit failed: {exc} - retry from the Library tab.")
                    status.update(label=f"{name} video ready: {out.name}", state="complete")
                st.video(str(out))
                if kit:
                    with st.expander(f"📋 {name} YouTube upload kit", expanded=True):
                        show_kit(kit, f"new-{out.name}")

# ---------------------------------------------------------------- 3. library
with library_tab:
    st.subheader("Packages and videos")
    packages = list_packages()
    if not packages:
        st.info("Nothing here yet.")
    for package_path in packages:
        package = load_package(package_path)
        with st.expander(f"**{package.topic}** · {package.level} · `{package_path.stem}`"):
            videos = [(lang, video_path(package_path, lang)) for lang in LANGUAGE_NAMES]
            videos = [(lang, path) for lang, path in videos if path.exists()]
            if videos:
                columns = st.columns(len(videos))
                for column, (lang, path) in zip(columns, videos):
                    with column:
                        st.markdown(f"**{LANGUAGE_NAMES[lang]}**")
                        st.video(str(path))
                        with path.open("rb") as fh:
                            st.download_button(
                                f"Download {path.name}", fh, file_name=path.name, mime="video/mp4",
                                key=f"dl-{path.name}",
                            )

                for lang, path in videos:
                    name = LANGUAGE_NAMES[lang]
                    st.markdown(f"#### 📋 {name} YouTube upload kit")
                    if not timings_path(str(path)).exists():
                        st.caption(
                            "This video was rendered before channel intros and scene timings existed - "
                            "re-render it in **2 · Make video** to get the intro and an upload kit."
                        )
                        continue
                    kit_file = kit_path(str(path))
                    kit = YouTubeKit.model_validate_json(kit_file.read_text(encoding="utf-8")) if kit_file.exists() else None
                    video_channel = json.loads(timings_path(str(path)).read_text(encoding="utf-8"))["channel"]
                    if st.button("Regenerate kit" if kit else "Create upload kit", key=f"kit-{path.name}"):
                        with st.spinner(f"Writing {name} YouTube kit..."):
                            try:
                                kit = make_kit(package_path, package, lang, path, video_channel)
                            except Exception as exc:
                                st.error(f"Kit failed: {exc}")
                    if kit:
                        show_kit(kit, path.name)
            else:
                st.caption("No videos rendered yet.")

            md_path = package_path.with_suffix(".md")
            if md_path.exists():
                st.download_button(
                    "Download full package (.md)", md_path.read_bytes(), file_name=md_path.name,
                    key=f"md-{md_path.name}",
                )
