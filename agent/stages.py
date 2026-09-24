import subprocess
import sys

from .client import call_structured
from .config import Config
from .models import (
    CodeExample,
    CodeOutput,
    CodeQAOutput,
    CodeQAResult,
    FinalQAOutput,
    MetadataOutput,
    ResearchOutput,
    ScriptOutput,
    StoryboardOutput,
)

CODING_TEACHER_SYSTEM = (
    "You are an expert coding instructor and YouTube educational content creator. "
    "You write for a technical audience that wants clear, correct, well-paced content. "
    "Be precise and avoid filler."
)


def run_research(client, config: Config, topic: str, level: str) -> ResearchOutput:
    system = CODING_TEACHER_SYSTEM
    user = (
        f"Research the coding topic '{topic}' for a {level}-level audience.\n"
        "Provide:\n"
        "- summary: a concise overview of the topic and why it matters\n"
        "- key_concepts: the core concepts a video must cover\n"
        "- common_misconceptions: mistakes or misunderstandings beginners/practitioners "
        "at this level commonly have about this topic\n"
        "- learning_objectives: 3-6 concrete, measurable things the viewer will be able "
        "to do after watching\n"
        "- prerequisites: what the viewer should already know before watching"
    )
    return call_structured(client, config, system, user, ResearchOutput)


def run_script(
    client, config: Config, topic: str, level: str, duration_minutes: int, research: ResearchOutput
) -> ScriptOutput:
    system = CODING_TEACHER_SYSTEM
    target_words = duration_minutes * 130
    user = (
        f"Write a YouTube video script for a {duration_minutes}-minute {level}-level "
        f"coding video on '{topic}'.\n\n"
        f"Research summary: {research.summary}\n"
        f"Key concepts to cover: {', '.join(research.key_concepts)}\n"
        f"Common misconceptions to address: {', '.join(research.common_misconceptions)}\n"
        f"Learning objectives: {', '.join(research.learning_objectives)}\n\n"
        "Provide:\n"
        f"- full_script: the complete narration script in markdown, written to fill the "
        f"full {duration_minutes} minutes when spoken at a natural pace (~130 words/minute). "
        f"This means a target of approximately {target_words} words - do not stop early; "
        f"go deeper into examples, edge cases, and explanation to reach this length rather "
        f"than padding with filler. Use clear section headers.\n"
        "- sections: a breakdown of the script into sections, each with a title, an "
        "estimated duration in seconds (these must sum to approximately "
        f"{duration_minutes * 60} seconds), and its narration text"
    )
    return call_structured(client, config, system, user, ScriptOutput, max_tokens=32000)


def run_code_examples(
    client, config: Config, topic: str, level: str, script: ScriptOutput
) -> CodeOutput:
    system = CODING_TEACHER_SYSTEM
    user = (
        f"Based on this video script about '{topic}' ({level} level), write the code "
        "examples that will be shown on screen.\n\n"
        f"Script:\n{script.full_script}\n\n"
        "For each example, provide:\n"
        "- title: what the example demonstrates\n"
        "- language: the programming language (use 'python' unless the topic clearly "
        "requires another language)\n"
        "- code: complete, runnable, self-contained code (no missing imports, no "
        "placeholders, must run standalone with no external files or network access)\n"
        "- expected_output: exactly what running this code should print to stdout\n"
        "- explanation: a short note on what the example teaches\n\n"
        "Order examples to match the script's flow, from simplest to most advanced."
    )
    return call_structured(client, config, system, user, CodeOutput, max_tokens=32000)


def run_code_qa(config: Config, code: CodeOutput) -> CodeQAOutput:
    """Actually execute each Python example locally and compare against the claimed
    expected_output, rather than asking the model to grade its own code."""
    results = []
    for example in code.examples:
        results.append(_execute_example(example, config.code_timeout_sec))

    if all(r.passed for r in results):
        overall = "All code examples executed successfully with no errors."
    else:
        failed = [r.title for r in results if not r.passed]
        overall = f"{len(failed)} example(s) failed execution: {', '.join(failed)}."

    return CodeQAOutput(results=results, overall_notes=overall)


def _execute_example(example: CodeExample, timeout_sec: int) -> CodeQAResult:
    if example.language.strip().lower() not in ("python", "py", "python3"):
        return CodeQAResult(
            title=example.title,
            passed=False,
            actual_output="[not executed: only Python examples are auto-executed in V1]",
            expected_output=example.expected_output,
            notes="Non-Python example - verify manually.",
        )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", example.code],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        actual = (proc.stdout + proc.stderr).strip()
        passed = proc.returncode == 0
        if passed:
            notes = "Executed successfully."
            if actual.strip() != example.expected_output.strip():
                notes += " Actual output differs from the script's claimed expected_output - review before publishing."
        else:
            notes = f"Exited with code {proc.returncode}."
    except subprocess.TimeoutExpired:
        actual = f"[timed out after {timeout_sec}s]"
        passed = False
        notes = "Execution exceeded the timeout - check for infinite loops or blocking input()."

    return CodeQAResult(
        title=example.title,
        passed=passed,
        actual_output=actual or "[no output]",
        expected_output=example.expected_output,
        notes=notes,
    )


def run_storyboard(
    client, config: Config, script: ScriptOutput, code: CodeOutput, code_qa: CodeQAOutput, duration_minutes: int
) -> StoryboardOutput:
    system = CODING_TEACHER_SYSTEM
    qa_lines = "\n".join(
        f"- {r.title}: {'PASSED' if r.passed else 'FAILED'} - {r.notes}" for r in code_qa.results
    )
    target_sec = duration_minutes * 60
    user = (
        "Turn this script and its code examples into a scene-by-scene storyboard for "
        "video production.\n\n"
        f"Script:\n{script.full_script}\n\n"
        f"Code examples: {', '.join(e.title for e in code.examples)}\n"
        f"Code QA results:\n{qa_lines}\n\n"
        "Break the script into scenes by covering it start to finish - every sentence of "
        "the script must appear in some scene's voiceover_line, in order, with nothing "
        "skipped or summarized away. Do not condense or shorten the narration.\n\n"
        "For each scene, provide:\n"
        "- scene_number: sequential integer starting at 1\n"
        "- voiceover_line: the exact narration spoken during this scene, copied verbatim "
        "from the script (not paraphrased or shortened)\n"
        "- duration_sec: the time in seconds to speak voiceover_line at ~130 words/minute "
        "(word_count / 130 * 60) - compute this from the actual voiceover_line text\n"
        "- visual_instructions: exactly what should be shown on screen (code editor, "
        "terminal, diagram, talking head, text overlay, etc.) and how it should transition\n"
        "- code_ref: the title of the code example shown in this scene, or an empty "
        "string if no code is shown\n\n"
        f"The scenes' duration_sec values must sum to approximately {target_sec} seconds "
        f"({duration_minutes} minutes), matching the full script length."
    )
    return call_structured(client, config, system, user, StoryboardOutput, max_tokens=32000)


def run_metadata(
    client, config: Config, topic: str, script: ScriptOutput, storyboard: StoryboardOutput
) -> MetadataOutput:
    system = "You are a YouTube SEO and content strategy expert for programming education channels."
    total_sec = sum(s.duration_sec for s in storyboard.scenes)
    user = (
        f"Create YouTube metadata for a coding tutorial on '{topic}' "
        f"(~{total_sec // 60} min runtime).\n\n"
        f"Script summary (first 500 chars): {script.full_script[:500]}\n\n"
        "Provide:\n"
        "- titles: 5 distinct title options, each under 70 characters, optimized for "
        "click-through without being misleading\n"
        "- description: a full YouTube description (2-4 paragraphs) including what "
        "viewers will learn\n"
        "- chapters: YouTube chapter markers as timestamp/label pairs starting at "
        "0:00, derived from the storyboard's scene structure\n"
        "- thumbnail_concepts: 3 distinct thumbnail concepts described in enough "
        "detail for a designer to execute"
    )
    return call_structured(client, config, system, user, MetadataOutput, max_tokens=16000)


def run_final_qa(client, config: Config, package_summary: str) -> FinalQAOutput:
    system = (
        "You are a meticulous video production QA reviewer for a programming "
        "education YouTube channel. You check for consistency, accuracy, and "
        "production-readiness across an entire video package."
    )
    user = (
        "Review this complete video production package for consistency and "
        "production-readiness. Check that the script, code examples, storyboard, and "
        "metadata all agree with each other, that the learning objectives are "
        "actually met by the script, and that nothing is missing.\n\n"
        f"{package_summary}\n\n"
        "Provide:\n"
        "- issues: a list of specific problems found (empty list if none)\n"
        "- overall_verdict: 'pass' if ready to produce, or 'needs_revision' if not\n"
        "- notes: any additional context for the production team"
    )
    return call_structured(client, config, system, user, FinalQAOutput, max_tokens=8000)
