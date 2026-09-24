from .client import get_client
from .config import Config
from .models import VideoPackage
from .stages import (
    run_code_examples,
    run_code_qa,
    run_final_qa,
    run_metadata,
    run_research,
    run_script,
    run_storyboard,
)


def run_pipeline(topic: str, level: str, duration_minutes: int, config: Config, log=print) -> VideoPackage:
    client = get_client()

    log(f"[1/7] Researching '{topic}' ({level})...")
    research = run_research(client, config, topic, level)

    log("[2/7] Writing script...")
    script = run_script(client, config, topic, level, duration_minutes, research)

    log("[3/7] Generating code examples...")
    code = run_code_examples(client, config, topic, level, script)

    if config.execute_code:
        log(f"[4/7] Executing {len(code.examples)} code example(s) locally for QA...")
    else:
        log("[4/7] Skipping code execution (VIDEO_AGENT_EXECUTE_CODE=0)...")
    code_qa = run_code_qa(config, code) if config.execute_code else _skip_qa(code)

    log("[5/7] Building storyboard...")
    storyboard = run_storyboard(client, config, script, code, code_qa, duration_minutes)

    log("[6/7] Generating YouTube metadata...")
    metadata = run_metadata(client, config, topic, script, storyboard)

    log("[7/7] Running final QA pass...")
    summary = _summarize_for_final_qa(topic, level, research, script, code, code_qa, storyboard, metadata)
    final_qa = run_final_qa(client, config, summary)

    return VideoPackage(
        topic=topic,
        level=level,
        duration_minutes=duration_minutes,
        research=research,
        script=script,
        code=code,
        code_qa=code_qa,
        storyboard=storyboard,
        metadata=metadata,
        final_qa=final_qa,
    )


def _skip_qa(code):
    from .models import CodeQAOutput, CodeQAResult

    results = [
        CodeQAResult(
            title=e.title,
            passed=False,
            actual_output="[not executed: code execution disabled]",
            expected_output=e.expected_output,
            notes="Code execution was disabled for this run.",
        )
        for e in code.examples
    ]
    return CodeQAOutput(results=results, overall_notes="Code execution was disabled for this run.")


def _summarize_for_final_qa(topic, level, research, script, code, code_qa, storyboard, metadata) -> str:
    return (
        f"Topic: {topic} ({level})\n"
        f"Learning objectives: {', '.join(research.learning_objectives)}\n"
        f"Script sections: {', '.join(s.title for s in script.sections)}\n"
        f"Code examples: {', '.join(e.title for e in code.examples)}\n"
        f"Code QA: {code_qa.overall_notes}\n"
        f"Storyboard scene count: {len(storyboard.scenes)}\n"
        f"Title options: {', '.join(metadata.titles)}\n"
        f"Chapters: {', '.join(c.label for c in metadata.chapters)}"
    )
