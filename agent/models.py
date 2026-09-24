from typing import List

from pydantic import BaseModel


class ResearchOutput(BaseModel):
    summary: str
    key_concepts: List[str]
    common_misconceptions: List[str]
    learning_objectives: List[str]
    prerequisites: List[str]


class ScriptSection(BaseModel):
    title: str
    duration_estimate_sec: int
    narration: str


class ScriptOutput(BaseModel):
    full_script: str
    sections: List[ScriptSection]


class CodeExample(BaseModel):
    title: str
    language: str
    code: str
    expected_output: str
    explanation: str


class CodeOutput(BaseModel):
    examples: List[CodeExample]


class CodeQAResult(BaseModel):
    title: str
    passed: bool
    actual_output: str
    expected_output: str
    notes: str


class CodeQAOutput(BaseModel):
    results: List[CodeQAResult]
    overall_notes: str


class StoryboardScene(BaseModel):
    scene_number: int
    duration_sec: int
    visual_instructions: str
    voiceover_line: str
    code_ref: str


class StoryboardOutput(BaseModel):
    scenes: List[StoryboardScene]


class Chapter(BaseModel):
    timestamp: str
    label: str


class MetadataOutput(BaseModel):
    titles: List[str]
    description: str
    chapters: List[Chapter]
    thumbnail_concepts: List[str]


class FinalQAOutput(BaseModel):
    issues: List[str]
    overall_verdict: str
    notes: str


class VideoPackage(BaseModel):
    topic: str
    level: str
    duration_minutes: int
    research: ResearchOutput
    script: ScriptOutput
    code: CodeOutput
    code_qa: CodeQAOutput
    storyboard: StoryboardOutput
    metadata: MetadataOutput
    final_qa: FinalQAOutput
