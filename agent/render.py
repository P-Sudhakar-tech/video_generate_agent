from .models import VideoPackage


def render_markdown(pkg: VideoPackage) -> str:
    parts = [
        f"# Video Package: {pkg.topic}",
        f"*Level: {pkg.level} | Target duration: {pkg.duration_minutes} min*",
        "",
        "## 01. Research",
        pkg.research.summary,
        "",
        "**Key concepts:**",
        _bullets(pkg.research.key_concepts),
        "",
        "**Common misconceptions:**",
        _bullets(pkg.research.common_misconceptions),
        "",
        "## 02. Learning Objectives",
        _bullets(pkg.research.learning_objectives),
        "",
        "## 03. Prerequisites",
        _bullets(pkg.research.prerequisites),
        "",
        "## 04. Script",
        pkg.script.full_script,
        "",
        "## 05. Code Examples",
        _render_code_examples(pkg),
        "",
        "## 06. Expected Outputs",
        _render_expected_outputs(pkg),
        "",
        "## 07. Code QA Report",
        _render_code_qa(pkg),
        "",
        "## 08. Scene-by-Scene Storyboard",
        _render_storyboard_table(pkg),
        "",
        "## 09. Voiceover Script",
        _render_voiceover(pkg),
        "",
        "## 10. Visual Instructions",
        _render_visual_instructions(pkg),
        "",
        "## 11. YouTube Title Options",
        _numbered(pkg.metadata.titles),
        "",
        "## 12. Description",
        pkg.metadata.description,
        "",
        "## 13. Chapters",
        _render_chapters(pkg),
        "",
        "## 14. Thumbnail Concepts",
        _numbered(pkg.metadata.thumbnail_concepts),
        "",
        "## 15. Final QA",
        _render_final_qa(pkg),
        "",
    ]
    return "\n".join(parts)


def _bullets(items):
    return "\n".join(f"- {item}" for item in items) or "- (none)"


def _numbered(items):
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1)) or "1. (none)"


def _render_code_examples(pkg: VideoPackage) -> str:
    blocks = []
    for ex in pkg.code.examples:
        blocks.append(
            f"### {ex.title}\n{ex.explanation}\n\n```{ex.language}\n{ex.code}\n```"
        )
    return "\n\n".join(blocks) or "(none)"


def _render_expected_outputs(pkg: VideoPackage) -> str:
    blocks = []
    for ex in pkg.code.examples:
        blocks.append(f"**{ex.title}**\n```\n{ex.expected_output}\n```")
    return "\n\n".join(blocks) or "(none)"


def _render_code_qa(pkg: VideoPackage) -> str:
    lines = [f"**Overall:** {pkg.code_qa.overall_notes}", "", "| Example | Passed | Notes |", "|---|---|---|"]
    for r in pkg.code_qa.results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"| {r.title} | {status} | {r.notes} |")
    lines.append("")
    for r in pkg.code_qa.results:
        lines.append(f"**{r.title} - actual output:**\n```\n{r.actual_output}\n```")
    return "\n".join(lines)


def _render_storyboard_table(pkg: VideoPackage) -> str:
    lines = ["| Scene | Duration (s) | Code Ref | Visual Instructions |", "|---|---|---|---|"]
    for s in pkg.storyboard.scenes:
        visual = s.visual_instructions.replace("\n", " ")
        lines.append(f"| {s.scene_number} | {s.duration_sec} | {s.code_ref or '-'} | {visual} |")
    return "\n".join(lines)


def _render_voiceover(pkg: VideoPackage) -> str:
    return "\n\n".join(f"**Scene {s.scene_number}:** {s.voiceover_line}" for s in pkg.storyboard.scenes)


def _render_visual_instructions(pkg: VideoPackage) -> str:
    return "\n\n".join(f"**Scene {s.scene_number}:** {s.visual_instructions}" for s in pkg.storyboard.scenes)


def _render_chapters(pkg: VideoPackage) -> str:
    return "\n".join(f"- {c.timestamp} {c.label}" for c in pkg.metadata.chapters) or "- (none)"


def _render_final_qa(pkg: VideoPackage) -> str:
    verdict = pkg.final_qa.overall_verdict.upper()
    lines = [f"**Verdict: {verdict}**", "", pkg.final_qa.notes, ""]
    if pkg.final_qa.issues:
        lines.append("**Issues found:**")
        lines.append(_bullets(pkg.final_qa.issues))
    else:
        lines.append("No issues found.")
    return "\n".join(lines)
