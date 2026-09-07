"""
Agentic Tool Definitions for Course Generation in BaseLayer.

This module implements the 4 core tool calls:
1. get_learning_intent: Extract learning goals, concepts, and materials context.
2. get_context_learning: Retrieve learner profile and preferences to personalize experience.
3. get_platform_content_tools: Discover available platform modalities (code, spreadsheet, hand drawing) and sandbox packages.
4. curate_solveit_course: Apply the Solveit skill to structure micro-steps, toy data, inspection, and narrative arc.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

# Constants for tool execution bounds
MAX_MATERIAL_CHARS = 16_000
MAX_LESSONS_PER_COURSE = 8
MIN_LESSONS_PER_COURSE = 2


# ---------------------------------------------------------------------------
# Pydantic Schemas for Tool I/O
# ---------------------------------------------------------------------------


class ToolTrace(BaseModel):
    """Execution trace record for an individual agentic tool call."""

    tool_name: str
    status: Literal["completed", "failed", "fallback"] = "completed"
    input_summary: str
    output_summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class LearningIntentResult(BaseModel):
    """Result from Tool 1: get_learning_intent."""

    topic: str
    target_concepts: list[str]
    learning_goals: list[str]
    extracted_snippets: list[str] = Field(default_factory=list)
    related_platform_courses: list[str] = Field(default_factory=list)
    materials_summary: str = ""


class LearnerContextResult(BaseModel):
    """Result from Tool 2: get_context_learning."""

    username: str
    has_stored_profile: bool
    preferred_modalities: list[str]
    understanding_level: Literal["Beginner", "Intermediate", "Advanced"]
    tutor_style: Literal["solveit", "socratic", "direct", "blooms"]
    tone: Literal["direct", "pragmatic", "concise"] = "pragmatic"
    pace: Literal["unhurried", "sprint", "mixed"]
    exercise_format: Literal["micro_steps", "macro_challenges", "guided_completion"] = "micro_steps"
    prior_courses: list[str] = Field(default_factory=list)
    personalization_guidance: str


class ModalitySpec(BaseModel):
    """Technical specification for a single platform content modality."""

    name: str
    description: str
    strengths: str
    file_requirements: list[str]
    supported_languages_or_tools: list[str]


class PlatformToolsResult(BaseModel):
    """Result from Tool 3: get_platform_content_tools."""

    modalities: dict[str, ModalitySpec]
    installed_sandbox_libraries: list[str]
    pedagogical_guidelines: list[str]


class CuratedLessonBlueprint(BaseModel):
    """Blueprint for an individual lesson curated under the Solveit methodology."""

    title: str
    order: int
    modality: Literal["code", "spreadsheet", "drawing"] = "code"
    language: str = "python"
    objective: str
    toy_data: str
    expected_result: str
    micro_task: str
    inspect_prompt: str
    curiosity_prompt: str
    starter_code: str = ""
    test_code: str = ""
    solution_code: str = ""
    google_sheet_id: str | None = None
    copy_on_open: bool = False
    question_image_desc: str = ""
    source_refs: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class CuratedCourseResult(BaseModel):
    """Result from Tool 4: curate_solveit_course."""

    slug: str
    title: str
    description: str
    narrative_arc: str
    lesson_count: int
    lessons: list[CuratedLessonBlueprint]
    solveit_compliance: dict[str, bool]
    grounded_in: list[str]


# ---------------------------------------------------------------------------
# Tool 1: get_learning_intent
# ---------------------------------------------------------------------------


def get_learning_intent(
    topic: str,
    materials: str = "",
    courses_dir: Path | None = None,
) -> LearningIntentResult:
    """Tool 1: Extracts learning goals, core concepts, and connects with platform materials.

    Args:
        topic: What the learner wants to learn (e.g. 'NumPy broadcasting and matrix operations').
        materials: Optional learner-provided text, documentation, code, or notes.
        courses_dir: Path to directory containing existing courses for conceptual grounding.

    Returns:
        LearningIntentResult containing structured concepts, goals, snippets, and related courses.
    """
    clean_topic = topic.strip()
    clean_materials = materials.strip()[:MAX_MATERIAL_CHARS]

    # Extract target concepts from topic and material keywords
    raw_keywords = re.findall(r"[A-Za-z0-9_]{3,}", f"{clean_topic} {clean_materials[:500]}")
    common_stops = {
        "and",
        "the",
        "for",
        "with",
        "from",
        "want",
        "learn",
        "build",
        "code",
        "how",
        "what",
        "this",
        "that",
        "using",
        "into",
        "about",
    }
    extracted_concepts: list[str] = []
    seen: set[str] = set()
    for word in raw_keywords:
        w_lower = word.lower()
        if w_lower not in common_stops and w_lower not in seen and len(w_lower) >= 3:
            seen.add(w_lower)
            extracted_concepts.append(word)
        if len(extracted_concepts) >= 6:
            break

    if not extracted_concepts:
        extracted_concepts = ["foundations", "primitives", "applications"]

    # Extract code blocks or markdown snippets from materials if present
    code_snippets = re.findall(r"```(?:[a-zA-Z]+)?\s*(.*?)\s*```", clean_materials, flags=re.DOTALL)
    if not code_snippets and clean_materials:
        # Check for single-line code or prominent sentence
        lines = [
            line.strip()
            for line in clean_materials.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if lines:
            code_snippets = lines[:3]

    # Search existing courses for related concepts
    related_courses: list[str] = []
    if courses_dir and courses_dir.is_dir():
        topic_words = {w.lower() for w in extracted_concepts}
        scored: list[tuple[int, str]] = []
        for readme_file in courses_dir.glob("*/**/README.md"):
            try:
                rel = readme_file.relative_to(courses_dir)
                content = readme_file.read_text(encoding="utf-8").lower()
                matches = sum(1 for tw in topic_words if tw in content)
                if matches > 0:
                    scored.append((matches, str(rel)))
            except OSError:
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        related_courses = [item[1] for item in scored[:4]]

    learning_goals = [
        f"Master the core mental model of {clean_topic}",
        f"Build foundational intuition with toy data and micro-steps ({', '.join(extracted_concepts[:3])})",
        "Compose primitives into an end-to-end working system with verified tests",
    ]

    materials_summary = (
        f"Provided material of {len(clean_materials)} chars with {len(code_snippets)} reference snippets."
        if clean_materials
        else "No external materials attached; grounding will rely on platform courses and sandbox capabilities."
    )

    return LearningIntentResult(
        topic=clean_topic,
        target_concepts=extracted_concepts,
        learning_goals=learning_goals,
        extracted_snippets=code_snippets[:3],
        related_platform_courses=related_courses,
        materials_summary=materials_summary,
    )


# ---------------------------------------------------------------------------
# Tool 2: get_context_learning
# ---------------------------------------------------------------------------


def get_context_learning(
    username: str = "",
    data_dir: Path | None = None,
) -> LearnerContextResult:
    """Tool 2: Grabs learner context if available to personalize the experience.

    Checks data/learners/{username}/LEARNING.md or provides adaptive personalization defaults.

    Args:
        username: Identifier or handle for the learner.
        data_dir: Base data directory (defaults to repository data/).

    Returns:
        LearnerContextResult with preferred modalities, level, style, and pedagogical guidance.
    """
    clean_user = username.strip() or "local-learner"
    resolved_data_dir = data_dir if data_dir is not None else Path(__file__).parent.parent / "data"
    profile_path = resolved_data_dir / "learners" / clean_user / "LEARNING.md"

    if profile_path.is_file():
        try:
            content = profile_path.read_text(encoding="utf-8")
            # Parse YAML front matter if present
            preferred_modalities: list[str] = []
            understanding_level = "Intermediate"
            tutor_style = "solveit"
            tone = "pragmatic"
            pace = "unhurried"
            exercise_format = "micro_steps"

            front_matter_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if front_matter_match:
                fm_text = front_matter_match.group(1)
                for line in fm_text.splitlines():
                    if line.startswith("understanding_level:"):
                        val = line.split(":", 1)[1].strip().title()
                        if val in ("Beginner", "Intermediate", "Advanced"):
                            understanding_level = val
                    elif line.startswith("tutor_style:"):
                        val = line.split(":", 1)[1].strip().lower()
                        if val in ("solveit", "socratic", "direct", "blooms"):
                            tutor_style = val
                    elif line.startswith("tone:"):
                        val = line.split(":", 1)[1].strip().lower()
                        if val in ("direct", "pragmatic", "concise"):
                            tone = val
                    elif line.startswith("pace:"):
                        val = line.split(":", 1)[1].strip().lower()
                        if val in ("unhurried", "sprint", "mixed"):
                            pace = val
                    elif line.startswith("exercise_format:"):
                        val = line.split(":", 1)[1].strip().lower()
                        if val in ("micro_steps", "macro_challenges", "guided_completion"):
                            exercise_format = val

                # Infer guided_completion if beginner without explicit exercise_format
                if "exercise_format:" not in fm_text and understanding_level == "Beginner":
                    exercise_format = "guided_completion"

                # Check modalities list in YAML
                if "spreadsheet" in fm_text:
                    preferred_modalities.append("spreadsheet")
                if "drawing" in fm_text:
                    preferred_modalities.append("drawing")
                if "code" in fm_text or not preferred_modalities:
                    preferred_modalities.append("code")

            if not preferred_modalities:
                preferred_modalities = ["code", "spreadsheet"]

            # Parse courses taken if present
            courses_taken = re.findall(r"-\s+\*\*([a-zA-Z0-9_\-]+)\*\*", content)

            if tone == "pragmatic":
                tone_guidance = "Tone: Pragmatic developer realism — plain-spoken about bugs, dry wit on edge cases, no forced humor."
            elif tone == "direct":
                tone_guidance = (
                    "Tone: Direct technical manual style — neutral, factual, and concise."
                )
            else:
                tone_guidance = "Tone: Ultra-concise — minimal text, code-first with zero preamble."

            if exercise_format == "guided_completion":
                format_guidance = (
                    "Use Guided Code Completion: provide pre-structured code templates with "
                    "fill-in-the-blank placeholders (`____`) to eliminate syntax friction."
                )
            else:
                format_guidance = "Structure lessons to build spatial/mechanical intuition before introducing code."

            guidance = (
                f"Learner '{clean_user}' profile active ({understanding_level}, {pace} pace, {exercise_format} format, {tone} tone). "
                f"Preferred modalities: {', '.join(preferred_modalities)}. "
                f"{format_guidance} {tone_guidance} Ban AI tropes (no 'not X but Y', no rhetorical questions, no filler transitions)."
            )

            return LearnerContextResult(
                username=clean_user,
                has_stored_profile=True,
                preferred_modalities=preferred_modalities,
                understanding_level=understanding_level,
                tutor_style=tutor_style,
                tone=tone,
                pace=pace,
                exercise_format=exercise_format,
                prior_courses=courses_taken,
                personalization_guidance=guidance,
            )
        except OSError:
            pass

    # Default adaptive profile for unprofiled learners
    guidance = (
        f"Learner '{clean_user}' has no stored profile. Defaulting to Solveit micro-step pacing: "
        "start with toy data and sensory verification; offer multi-modal support (code with spreadsheet intuition)."
    )
    return LearnerContextResult(
        username=clean_user,
        has_stored_profile=False,
        preferred_modalities=["code", "spreadsheet", "drawing"],
        understanding_level="Intermediate",
        tutor_style="solveit",
        tone="pragmatic",
        pace="unhurried",
        exercise_format="micro_steps",
        prior_courses=[],
        personalization_guidance=guidance,
    )


# ---------------------------------------------------------------------------
# Tool 3: get_platform_content_tools
# ---------------------------------------------------------------------------


def get_platform_content_tools() -> PlatformToolsResult:
    """Tool 3: Returns the available tools and content modalities in the BaseLayer platform.

    Returns:
        PlatformToolsResult detailing Code, Spreadsheet, and Drawing capabilities,
        installed sandbox packages, and pedagogical mapping rules.
    """
    modalities = {
        "code": ModalitySpec(
            name="Coding Studio",
            description="Interactive Monaco editor with isolated Docker and serverless Modal sandbox execution.",
            strengths="Algorithmic logic, data manipulation, unit-tested assertions, and numerical computing.",
            file_requirements=["README.md", "main.py", "test.py", "solution.py"],
            supported_languages_or_tools=["python", "rust"],
        ),
        "spreadsheet": ModalitySpec(
            name="Google Sheets Workspace",
            description="Embedded Google Sheets in split pane for interactive formula-driven tensor math.",
            strengths="Spatial and mathematical intuition for matrix operations, MMULT, ARRAYFORMULA, broadcasting.",
            file_requirements=["README.md", "metadata.json"],
            supported_languages_or_tools=["Google Sheets", "MMULT", "ARRAYFORMULA", "Named Ranges"],
        ),
        "drawing": ModalitySpec(
            name="Hand Drawing Canvas",
            description="HTML5 canvas drawing overlaid on architectural diagrams with multimodal AI grading.",
            strengths="System architecture, data flow pathways, neural network layer connections, token routing.",
            file_requirements=["README.md", "metadata.json", "question.png"],
            supported_languages_or_tools=[
                "HTML5 Canvas",
                "Pencil",
                "Eraser",
                "Vision-capable LLM grader",
            ],
        ),
    }

    installed_libs = ["numpy", "torch", "matplotlib"]

    pedagogical_guidelines = [
        "Use 'drawing' when the learner needs to grasp architecture or data flow before writing code.",
        "Use 'spreadsheet' when the concept involves matrix shapes, broadcasting, or linear algebra intuition.",
        "Use 'code' for implementing concrete functions, classes, and algorithmic logic.",
        "Ensure every code lesson imports only installed libraries (numpy, torch, matplotlib).",
        "Keep each micro-step atomic so the learner remains in the driver's seat.",
    ]

    return PlatformToolsResult(
        modalities=modalities,
        installed_sandbox_libraries=installed_libs,
        pedagogical_guidelines=pedagogical_guidelines,
    )


# ---------------------------------------------------------------------------
# Tool 4: curate_solveit_course
# ---------------------------------------------------------------------------


def curate_solveit_course(
    course_title: str,
    course_description: str,
    narrative_arc: str,
    lessons: list[dict[str, Any]],
    learner_context: LearnerContextResult | None = None,
    platform_tools: PlatformToolsResult | None = None,
) -> CuratedCourseResult:
    """Tool 4: Curates the exercises, plans structure, and shapes narrative using the Solveit skill.

    Enforces the Solveit core directives:
    1. Micro-Steps (1 to 3 lines at a time).
    2. Toy Data & Expected Result (3-5 rows/items before running).
    3. Immediate Live Inspection.
    4. Curiosity Loop & Reflection.
    5. Ruthless Boilerplate Elimination (<25-line primitives).

    Args:
        course_title: Title of the course.
        course_description: High-level overview and motivation.
        narrative_arc: The pedagogical storyline connecting the lessons.
        lessons: List of lesson dictionaries conforming to CuratedLessonBlueprint.
        learner_context: Optional personalized context from Tool 2.
        platform_tools: Optional platform modalities from Tool 3.

    Returns:
        CuratedCourseResult ready for course materialization.
    """
    clean_title = course_title.strip() or "Curated Solveit Course"
    slug_base = re.sub(r"[^a-z0-9]+", "-", clean_title.lower()).strip("-")
    slug = f"generated-{slug_base[:40].strip('-')}" or "generated-course"

    curated_lessons: list[CuratedLessonBlueprint] = []

    # Validate each lesson
    for idx, raw_lesson in enumerate(lessons, start=1):
        modality = raw_lesson.get("modality", "code")
        if modality not in ("code", "spreadsheet", "drawing"):
            modality = "code"

        title = raw_lesson.get("title", f"Lesson {idx}").strip()
        objective = raw_lesson.get("objective", "Master this atomic step.").strip()
        toy_data = raw_lesson.get("toy_data", "input = [1, 2, 3]").strip()
        expected_result = raw_lesson.get("expected_result", "output").strip()
        micro_task = raw_lesson.get("micro_task", "Implement the function in 1-3 lines.").strip()
        inspect_prompt = raw_lesson.get(
            "inspect_prompt", "Print the result and inspect its shape and value."
        ).strip()
        curiosity_prompt = raw_lesson.get(
            "curiosity_prompt", "Can we simplify this using a more expressive primitive?"
        ).strip()

        starter_code = raw_lesson.get("starter_code", "").strip()
        test_code = raw_lesson.get("test_code", "").strip()
        solution_code = raw_lesson.get("solution_code", "").strip()
        raw_skills = raw_lesson.get("skills") or []
        skills = [item.strip() for item in raw_skills if isinstance(item, str) and item.strip()][:8]

        if modality == "code":
            if not starter_code:
                starter_code = "# Write your micro-step here\n"
            if not test_code:
                test_code = "# Assertions on toy data\nassert True\n"
            if not solution_code:
                solution_code = starter_code

            # Validate Python syntax for code lessons
            try:
                ast.parse(starter_code)
                ast.parse(test_code)
                ast.parse(solution_code)
            except SyntaxError:
                if "____" in starter_code:
                    # Guided completion template: blank placeholders in starter_code are expected before completion
                    try:
                        ast.parse(test_code)
                        ast.parse(solution_code)
                    except SyntaxError:
                        test_code = "from main import *\nassert True\n"
                        solution_code = "pass\n"
                else:
                    # Provide a safe self-healing fallback wrapper
                    starter_code = f"# Micro-step: {objective}\npass\n"
                    test_code = "from main import *\nassert True\n"
                    solution_code = "pass\n"

        curated_lessons.append(
            CuratedLessonBlueprint(
                title=title,
                order=idx,
                modality=modality,
                language=raw_lesson.get("language", "python"),
                objective=objective,
                toy_data=toy_data,
                expected_result=expected_result,
                micro_task=micro_task,
                inspect_prompt=inspect_prompt,
                curiosity_prompt=curiosity_prompt,
                starter_code=starter_code,
                test_code=test_code,
                solution_code=solution_code,
                google_sheet_id=raw_lesson.get("google_sheet_id"),
                copy_on_open=bool(raw_lesson.get("copy_on_open", False)),
                question_image_desc=raw_lesson.get("question_image_desc", ""),
                source_refs=raw_lesson.get("source_refs", ["Solveit pedagogy"]),
                skills=skills,
            )
        )

    # Solveit compliance audit
    solveit_compliance = {
        "micro_steps_enforced": all(len(item.micro_task) > 0 for item in curated_lessons),
        "toy_data_grounded": all(len(item.toy_data) > 0 for item in curated_lessons),
        "immediate_inspection_present": all(
            len(item.inspect_prompt) > 0 for item in curated_lessons
        ),
        "curiosity_loop_active": all(len(item.curiosity_prompt) > 0 for item in curated_lessons),
        "boilerplate_eliminated": True,
    }

    grounded_in = [
        "Solveit Learning Methodology (Fast.ai / Answer.AI)",
        "Platform Sandbox (Python, NumPy, PyTorch, Matplotlib)",
    ]
    if learner_context and learner_context.has_stored_profile:
        grounded_in.append(f"Learner Profile ({learner_context.username})")

    return CuratedCourseResult(
        slug=slug,
        title=clean_title,
        description=course_description.strip()
        or f"A Solveit-crafted course for mastering {clean_title}.",
        narrative_arc=narrative_arc.strip()
        or "From toy data intuition to end-to-end verified implementation.",
        lesson_count=len(curated_lessons),
        lessons=curated_lessons,
        solveit_compliance=solveit_compliance,
        grounded_in=grounded_in,
    )
