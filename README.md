# video_generate_agent

An AI agent that turns a coding topic (for example *"Python Variables"*) into a ready-to-upload YouTube tutorial. It researches the topic, writes the script and code examples, runs the code to check it, builds a storyboard, and renders a narrated MP4 in **English** and/or **Telugu**. It also writes a YouTube upload kit with titles, description, tags, chapters, thumbnail ideas and a pinned comment.

It uses Google Gemini, which has a free tier, for text and Microsoft Edge neural voices (free, no API key) for narration. You can run it from a Streamlit web UI or from the command line.

## Features

- **7-stage content pipeline**: research → script → code examples → code QA → storyboard → YouTube metadata → final QA.
- **Code examples are actually run**: each Python example is executed locally and its output is compared with the expected output. The model does not grade its own code.
- **Narrated video rendering**: 1920×1080 slides (syntax-highlighted code with captions, or title cards) with a voiceover, combined into one MP4.
- **Channel intro**: every video opens with a like/share/subscribe intro that uses your channel name.
- **Telugu support**: the narration is translated into conversational Telugu. Programming terms stay in English and the code slides are unchanged.
- **YouTube upload kit**: chapter timestamps are taken from the real scene timings of the rendered video. The description, tags and hashtags follow YouTube's limits.
- **Built for the free tier**: calls are retried with backoff on rate limits and overloads, each call has a hard timeout, and scene audio is cached so an interrupted render can be resumed.

## How it works

```
topic ──► main.py / UI "Create package"
            1. Research          (summary, key concepts, misconceptions, objectives)
            2. Script            (~130 words per minute of target duration)
            3. Code examples     (runnable, self-contained)
            4. Code QA           (runs each Python example locally)
            5. Storyboard        (scene-by-scene voiceover + visuals)
            6. YouTube metadata
            7. Final QA          (consistency check across the package)
          ──► outputs/<topic>.json + <topic>.md

<topic>.json ──► make_video.py / UI "Make video"
            translate (if not English, cached) ──► TTS per scene ──► slides
          ──► outputs/<topic>.mp4, <topic>.te.mp4 + YouTube upload kit
```

## Requirements

- Python 3.10+ (developed on 3.11)
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/api-keys)
- An internet connection (Gemini and Edge TTS are online services)

You don't need to install FFmpeg separately, because `moviepy` includes one through `imageio-ffmpeg`.

> **Platform note:** the project is developed on Windows. Telugu text on slides requires Pillow's `raqm` text shaping. On Windows this works through the bundled `vendor/fribidi-0.dll` and the built-in Nirmala UI font. On Linux or macOS, install `libraqm` and a Telugu-capable font. English videos work on any platform.

## Setup

```bash
git clone https://github.com/P-Sudhakar-tech/video_generate_agent.git
cd video_generate_agent

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Copy the example environment file and add your key:

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

```env
GEMINI_API_KEY=AIza...
```

Check that the key and model work:

```bash
python main.py --check
```

## Usage

### Web UI (recommended)

```bash
streamlit run app.py
```

Enter your **channel name** in the sidebar, then use the three tabs:

1. **Create package**: enter a topic, level and target duration, then generate the script, code, storyboard and metadata.
2. **Make video**: pick a package, one or more languages and a voice engine, then render. The YouTube upload kit is generated after each video and every field has a copy button.
3. **Library**: watch or download rendered videos, regenerate upload kits, and download the full package as Markdown.

### Command line

**Step 1: generate the content package**

```bash
python main.py --topic "Python Variables" --level Beginner --duration 8
```

| Option | Description |
|---|---|
| `--topic` | Video topic (required unless `--check`) |
| `--level` | `Beginner` (default), `Intermediate` or `Advanced` |
| `--duration` | Target length in minutes (default `8`) |
| `--model` | Override the Gemini model |
| `--no-execute` | Don't run the generated code examples locally |
| `--output` | Custom path for the Markdown file (the JSON is written next to it) |
| `--check` | Verify the API key and model with one small call, then exit |

**Step 2: render the video(s)**

```bash
python make_video.py outputs/python-variables.json --channel "CodeForge" --lang en te
```

| Option | Description |
|---|---|
| `package` | Path to the `<topic>.json` created in step 1 |
| `--channel` | Your channel name, used in the intro and the upload kit (required) |
| `--lang` | One or more of `en`, `te`. One video is rendered per language (default `en`) |
| `--tts` | `edge` (default, free, no daily limit) or `gemini` (10 requests/day on the free tier) |
| `--output` | Custom MP4 path (only when rendering a single language) |
| `--no-kit` | Skip generating the YouTube upload kit |

## Output files

Everything is written to `outputs/` (configurable):

| File | Contents |
|---|---|
| `<topic>.json` | The full video package. Step 2 reads this file |
| `<topic>.md` | The same package as a readable document: research, script, code, QA report, storyboard, metadata |
| `<topic>.mp4` / `<topic>.te.mp4` | The rendered English / Telugu video |
| `<topic>.te.json` | Cached Telugu translation. Edit it to fix wording, then re-render |
| `<topic>[.te].timings.json` | Start time of each scene, used for chapter timestamps |
| `<topic>[.te].youtube.json` / `.youtube.md` | YouTube upload kit |
| `<topic>_scenes/` | Cached scene audio and frames, reused on re-render |

## Configuration

All settings are optional environment variables and can go in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | **Required.** Gemini API key |
| `VIDEO_AGENT_MODEL` | `gemini-flash-lite-latest` | Text model for the pipeline, translation and upload kit |
| `VIDEO_AGENT_TTS_ENGINE` | `edge` | `edge` or `gemini` |
| `VIDEO_AGENT_EDGE_VOICE` | *(per language)* | Edge voice. Defaults to `en-IN-PrabhatNeural` / `te-IN-MohanNeural` |
| `VIDEO_AGENT_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | Gemini TTS model |
| `VIDEO_AGENT_TTS_VOICE` | `Kore` | Gemini TTS voice |
| `VIDEO_AGENT_EXECUTE_CODE` | `1` | Set to `0` to skip running code examples |
| `VIDEO_AGENT_CODE_TIMEOUT` | `10` | Seconds allowed per code example |
| `VIDEO_AGENT_OUTPUT_DIR` | `outputs` | Output folder |
| `VIDEO_AGENT_MAX_TOKENS` | `16000` | Default output token budget per call |
| `VIDEO_AGENT_MAX_RETRIES` | `3` | Retries on rate-limit or overload errors |
| `VIDEO_AGENT_CALL_TIMEOUT` | `90` | Hard timeout in seconds per API call |

## Project structure

```
├── app.py              # Streamlit web UI
├── main.py             # CLI: topic → content package (.json + .md)
├── make_video.py       # CLI: content package → MP4 + YouTube kit
├── agent/
│   ├── pipeline.py     # Runs the 7 pipeline stages in order
│   ├── stages.py       # Prompts for each stage + local code execution
│   ├── models.py       # Pydantic schemas for every stage's output
│   ├── client.py       # Gemini client, structured output, retries, hard timeouts
│   ├── config.py       # Settings from environment variables
│   ├── render.py       # Package → Markdown document
│   ├── translate.py    # Narration translation (Telugu)
│   ├── tts.py          # Text-to-speech (Edge / Gemini)
│   ├── visuals.py      # Slide rendering with Pillow (code, title, intro)
│   ├── video.py        # Assembles narrated scenes into an MP4 (moviepy)
│   ├── branding.py     # Like/share/subscribe intro templates
│   └── youtube.py      # YouTube upload kit generation
└── vendor/
    └── fribidi-0.dll   # Enables Telugu text shaping in Pillow on Windows
```

## Notes and limitations

- **Code execution is not sandboxed.** Code QA runs the LLM-generated Python on your machine with only a timeout. Use `--no-execute` (or uncheck the option in the UI) if that is a concern.
- Only Python examples are run automatically. Examples in other languages are marked for manual review.
- The generated content is AI-written. Read the `.md` package, and especially the Code QA and Final QA sections, before you publish.
- When uploading, mark the video as containing **altered or synthetic content** because the narration uses an AI voice. The upload kit checklist includes this step.

## License

This project is licensed under the [Apache License 2.0](LICENSE).
