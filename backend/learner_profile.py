"""
Learner Profile Manager for BaseLayer (Issue #23).

Stores learning style, course activity, struggles, and preferences
in human-readable, editable markdown files at:
  data/learners/{username}/LEARNING.md
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


def get_learners_data_dir() -> Path:
    """Resolve data directory for learners."""
    override = os.environ.get("LEARNERS_DATA_DIR")
    if override:
        return Path(override)
    # Default to data/ directory under repo root
    return Path(__file__).resolve().parent.parent / "data" / "learners"


class LearnerFrontMatter(BaseModel):
    username: str
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1
    preferred_ui: Literal["classic", "light"] = "light"
    tutor_style: Literal["solveit", "socratic", "direct", "blooms"] = "solveit"
    tone: Literal["direct", "pragmatic", "concise"] = "pragmatic"
    understanding_level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    preferred_modalities: list[str] = Field(
        default_factory=lambda: ["code", "spreadsheet", "drawing"]
    )
    pace: Literal["unhurried", "sprint", "mixed"] = "unhurried"
    explanation_length: Literal["short", "thorough"] = "short"
    exercise_format: Literal["micro_steps", "macro_challenges", "guided_completion"] = "micro_steps"


class LearnerProfileData(BaseModel):
    frontmatter: LearnerFrontMatter
    snapshot: str = ""
    courses_taken: list[str] = Field(default_factory=list)
    courses_built: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    customize_next: list[str] = Field(default_factory=list)


class LearnerQuestionnaire(BaseModel):
    # Simplified Zero-Jargon Diagnostic Choices
    intake_preference: Literal["diagram", "table", "hands_on", "story"] | None = Field(
        default=None,
        description="What makes a new concept click: diagram (visual), table (spreadsheet), hands_on (code), story (text).",
    )
    explanation_length: Literal["short", "thorough"] = Field(
        default="short",
        description="Explanation length: short (concise essentials) or thorough (detailed with analogies).",
    )
    exercise_format: Literal["micro_steps", "macro_challenges", "guided_completion"] | None = Field(
        default=None,
        description="Exercise structure: micro_steps (bite-sized verified steps), macro_challenges (larger puzzles), or guided_completion (scaffolded fill-in-the-blanks).",
    )
    hint_preference: Literal["toy_example", "guiding_question", "direct_explanation"] | None = (
        Field(
            default=None,
            description="Support when stuck: toy_example (Solveit), guiding_question (Socratic), direct_explanation (Direct).",
        )
    )
    tone: Literal["direct", "pragmatic", "concise"] = Field(
        default="pragmatic",
        description="Explanation tone: pragmatic (dry developer realism), direct (neutral technical manual), concise (minimal text).",
    )
    # Core preferences (direct or inferred)
    goal: str = Field(
        default="Understand foundational AI and systems from first principles",
        min_length=3,
        max_length=500,
    )
    preferred_modalities: list[str] = Field(
        default_factory=lambda: ["code", "spreadsheet", "drawing"]
    )
    understanding_level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    tutor_style: Literal["solveit", "socratic", "direct", "blooms"] = "solveit"
    pace: Literal["unhurried", "sprint", "mixed"] = "unhurried"
    preferred_ui: Literal["classic", "light"] = "light"
    custom_notes: str = Field(default="", max_length=1000)


def _default_profile_markdown(username: str) -> str:
    now_iso = datetime.now(timezone.utc).isoformat()
    return f"""---
username: {username}
updated_at: {now_iso}
version: 1
preferred_ui: light
tutor_style: solveit
tone: pragmatic
understanding_level: intermediate
preferred_modalities:
  - code
  - spreadsheet
  - drawing
pace: unhurried
explanation_length: short
exercise_format: micro_steps
---

# Learning profile — {username}

## Snapshot
Exploratory learner using the Solveit methodology: building from toy data and verified micro-steps.

## Courses taken

## Courses built

## Signals
- Initialized learning profile.

## Customize next
- Default SocratiQ to Solveit tutoring.
- Offer spreadsheet or drawing intuition warm-up for tensor lessons.
"""


def _parse_scalar_value(val: str) -> Any:
    cleaned = val.split(" #", 1)[0].strip() if " #" in val else val.strip()
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned.lower() in ("true", "false"):
        return cleaned.lower() == "true"
    return cleaned


def _assign_frontmatter_kv(line: str, parsed_fm: dict[str, Any]) -> str | None:
    key, val = line.split(":", 1)
    key = key.strip()
    val = val.strip()
    if not val:
        parsed_fm[key] = []
        return key
    parsed_fm[key] = _parse_scalar_value(val)
    return None


def _is_ignorable_fm_line(line: str) -> bool:
    trimmed = line.strip()
    return not trimmed or trimmed.startswith("#")


def _append_list_item(trimmed: str, parsed_fm: dict[str, Any], key: str | None) -> bool:
    if key and trimmed.startswith("- "):
        parsed_fm.setdefault(key, []).append(trimmed[2:].strip())
        return True
    return False


def _process_frontmatter_line(
    line: str, parsed_fm: dict[str, Any], current_list_key: str | None
) -> str | None:
    if _is_ignorable_fm_line(line):
        return current_list_key

    trimmed = line.strip()
    if _append_list_item(trimmed, parsed_fm, current_list_key):
        return current_list_key

    if ":" in line:
        return _assign_frontmatter_kv(line, parsed_fm)

    return current_list_key


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML-like frontmatter and body markdown."""
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError("Invalid LEARNING.md: Missing '---' YAML front matter block.")

    fm_text = match.group(1)
    body = match.group(2)

    parsed_fm: dict[str, Any] = {}
    current_list_key: str | None = None

    for line in fm_text.splitlines():
        current_list_key = _process_frontmatter_line(line, parsed_fm, current_list_key)

    return parsed_fm, body


def serialize_frontmatter(fm: LearnerFrontMatter) -> str:
    """Serializes LearnerFrontMatter into YAML frontmatter string."""
    modalities_yaml = "\n".join(f"  - {m}" for m in fm.preferred_modalities)
    return f"""---
username: {fm.username}
updated_at: {fm.updated_at}
version: {fm.version}
preferred_ui: {fm.preferred_ui}
tutor_style: {fm.tutor_style}
tone: {fm.tone}
understanding_level: {fm.understanding_level}
preferred_modalities:
{modalities_yaml}
pace: {fm.pace}
explanation_length: {fm.explanation_length}
exercise_format: {fm.exercise_format}
---"""


def parse_markdown_sections(body: str) -> dict[str, list[str]]:
    """Parses markdown body into a dictionary of section names to lines."""
    sections: dict[str, list[str]] = {}
    current_section: str = "Intro"

    for line in body.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections[current_section] = []
        else:
            sections.setdefault(current_section, []).append(line)

    return sections


def get_profile_path(username: str, base_dir: Path | None = None) -> Path:
    """Returns the path to data/learners/{username}/LEARNING.md."""
    clean_name = re.sub(r"[^a-zA-Z0-9_\-]+", "-", username.strip().lower()).strip("-") or "learner"
    root = base_dir if base_dir is not None else get_learners_data_dir()
    return root / clean_name / "LEARNING.md"


def _extract_bullet_items(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip().startswith("- ")]


def get_or_create_profile(
    username: str, base_dir: Path | None = None
) -> tuple[str, dict[str, Any]]:
    """Reads LEARNING.md if present, or creates initial file and returns (markdown, parsed)."""
    file_path = get_profile_path(username, base_dir)
    if not file_path.is_file():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = _default_profile_markdown(username)
        file_path.write_text(content, encoding="utf-8")

    content = file_path.read_text(encoding="utf-8")
    fm_raw, body = parse_frontmatter(content)
    fm = LearnerFrontMatter.model_validate(fm_raw)
    sections = parse_markdown_sections(body)

    return content, {
        "frontmatter": fm.model_dump(),
        "snapshot": "\n".join(sections.get("Snapshot", [])).strip(),
        "courses_taken": _extract_bullet_items(sections.get("Courses taken", [])),
        "courses_built": _extract_bullet_items(sections.get("Courses built", [])),
        "signals": _extract_bullet_items(sections.get("Signals", [])),
        "customize_next": _extract_bullet_items(sections.get("Customize next", [])),
    }


def update_profile_markdown(
    username: str, markdown: str, base_dir: Path | None = None
) -> tuple[str, dict[str, Any]]:
    """Validates frontmatter and saves user edits to LEARNING.md."""
    fm_raw, body = parse_frontmatter(markdown)
    # Ensure username in frontmatter matches authenticated user
    fm_raw["username"] = username
    fm_raw["updated_at"] = datetime.now(timezone.utc).isoformat()
    fm = LearnerFrontMatter.model_validate(fm_raw)

    file_path = get_profile_path(username, base_dir)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Reconstruct with validated frontmatter
    validated_content = f"{serialize_frontmatter(fm)}\n\n{body.strip()}\n"
    file_path.write_text(validated_content, encoding="utf-8")

    return get_or_create_profile(username, base_dir)


@dataclass
class CourseTaken:
    """Structured view of a single 'Courses taken' bullet in LEARNING.md."""

    course_slug: str
    last_lesson: str | None = None
    done: list[str] = field(default_factory=list)
    xp: int = 0
    total: int | None = None
    completed: bool = False


# Canonical bullet format (human readable + parseable):
#   - **{course}** — in progress (2/6). Last: chapter1--lesson03. Done: a, b. XP: 60.
_COURSE_TAKEN_RE = re.compile(
    r"^-\s*\*\*(?P<course>[a-zA-Z0-9_-]+)\*\*\s*[—–-]\s*"
    r"(?P<status>in progress|completed)\s*\((?P<count>[^()]*)\)\s*\.\s*"
    r"Last:\s*(?P<last>[\w./-]+)\s*\.\s*"
    r"Done:\s*(?P<done>.*?)\s*\.\s*"
    r"XP:\s*(?P<xp>\d+)\s*\.?\s*$"
)
# Legacy bullet written before per-course progress existed:
#   - **{course}** — chapter1--lesson02 (in progress).
_COURSE_TAKEN_LEGACY_RE = re.compile(
    r"^-\s*\*\*(?P<course>[a-zA-Z0-9_-]+)\*\*\s*[—–-]\s*"
    r"(?P<last>[\w./-]+)\s*"
    r"\((?P<status>in progress|completed)\)\.?\s*$"
)
_COURSE_COUNT_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def _slug_list(text: str) -> list[str]:
    """Split a comma separated list of lesson slugs, keeping only valid tokens."""
    result: list[str] = []
    for token in text.split(","):
        token = token.strip()
        if token in ("", "none"):
            continue
        if re.fullmatch(r"[a-zA-Z0-9_-]+(?:--[a-zA-Z0-9_-]+)?", token):
            result.append(token)
    return result


def parse_course_taken_line(line: str) -> CourseTaken | None:
    """Parse a 'Courses taken' bullet into a CourseTaken (new or legacy format)."""
    match = _COURSE_TAKEN_RE.match(line.strip())
    if match:
        count = match.group("count")
        count_match = _COURSE_COUNT_RE.search(count)
        total = int(count_match.group(2)) if count_match else None
        return CourseTaken(
            course_slug=match.group("course"),
            last_lesson=match.group("last") if match.group("last") != "n/a" else None,
            done=_slug_list(match.group("done")),
            xp=int(match.group("xp")),
            total=total,
            completed=match.group("status") == "completed",
        )

    legacy = _COURSE_TAKEN_LEGACY_RE.match(line.strip())
    if legacy:
        return CourseTaken(
            course_slug=legacy.group("course"),
            last_lesson=legacy.group("last"),
            completed=legacy.group("status") == "completed",
        )

    return None


def format_course_taken_line(entry: CourseTaken) -> str:
    """Render a CourseTaken as a single human-readable 'Courses taken' bullet."""
    done_count = len(entry.done)
    if entry.total:
        label = f"{'completed' if entry.completed else 'in progress'} ({done_count}/{entry.total})"
    else:
        label = (
            f"{'completed' if entry.completed else 'in progress'} "
            f"({done_count} lesson{'s' if done_count != 1 else ''} done)"
        )
    last = entry.last_lesson or "n/a"
    done_text = ", ".join(entry.done) if entry.done else "none"
    return f"- **{entry.course_slug}** — {label}. Last: {last}. Done: {done_text}. XP: {entry.xp}."


def _course_catalog(course_slug: str) -> list[tuple[str, int, str]] | None:
    """Return [(slug, order, title)] for a file course, or None when unavailable."""
    try:
        from routers.file_courses import parse_course
    except Exception:
        return None
    try:
        course = parse_course(course_slug)
    except Exception:
        return None
    if course is None:
        return None
    return [(lesson.slug, lesson.order, lesson.title) for lesson in course.lessons]


def _refresh_course_status(entry: CourseTaken, course_slug: str) -> None:
    """Sync total/completed against the course catalog when it can be resolved."""
    catalog = _course_catalog(course_slug)
    if catalog is None:
        # No catalog (e.g. offline or deleted course): trust stored counts but do not
        # over-claim completion if the stored total has since grown beyond what we know.
        if entry.total is not None and entry.completed and len(entry.done) < entry.total:
            entry.completed = False
        return
    entry.total = len(catalog)
    known = {slug for slug, _order, _title in catalog}
    entry.completed = bool(known) and known.issubset(set(entry.done))


def _load_course_taken(sections: dict[str, list[str]], course_slug: str) -> CourseTaken:
    """Find the existing Courses-taken entry for a course, migrating legacy bullets."""
    taken = sections.setdefault("Courses taken", [])
    prefix = f"- **{course_slug}**"
    for idx, line in enumerate(taken):
        if line.strip().startswith(prefix):
            parsed = parse_course_taken_line(line)
            if parsed is not None:
                return parsed
            # Unparseable but same-course bullet: replace it with a fresh entry.
            fresh = CourseTaken(course_slug=course_slug)
            taken[idx] = format_course_taken_line(fresh)
            sections["Courses taken"] = taken
            return fresh
    return CourseTaken(course_slug=course_slug)


def _write_course_taken(sections: dict[str, list[str]], entry: CourseTaken) -> None:
    """Upsert the CourseTaken bullet, preserving list position."""
    taken = sections.setdefault("Courses taken", [])
    prefix = f"- **{entry.course_slug}**"
    line = format_course_taken_line(entry)
    for idx, existing in enumerate(taken):
        if existing.strip().startswith(prefix):
            taken[idx] = line
            sections["Courses taken"] = taken
            return
    taken.append(line)
    sections["Courses taken"] = taken


def _payload_xp(payload: dict[str, Any]) -> int:
    raw = payload.get("xp", 35)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 35


def _handle_lesson_opened(
    fm: LearnerFrontMatter, sections: dict[str, list[str]], payload: dict[str, Any]
) -> None:
    ui = payload.get("ui")
    if ui in ("classic", "light"):
        fm.preferred_ui = ui

    course_slug = payload.get("course_slug", "")
    lesson_slug = payload.get("lesson_slug", "")
    if not course_slug or not lesson_slug:
        return

    entry = _load_course_taken(sections, course_slug)
    entry.last_lesson = lesson_slug
    _refresh_course_status(entry, course_slug)
    _write_course_taken(sections, entry)


def _handle_run_result(sections: dict[str, list[str]], payload: dict[str, Any]) -> None:
    if not payload.get("is_submit", False):
        return

    course_slug = payload.get("course_slug", "")
    lesson_slug = payload.get("lesson_slug", "")
    # Only meaningful when the run is attached to a known course/lesson.
    if not course_slug or not lesson_slug:
        return

    language = payload.get("language", "python")
    signals = sections.get("Signals", [])

    if payload.get("success", False):
        signal_text = f"- Completed {course_slug} ({lesson_slug}) with passing {language} tests."
    else:
        signal_text = f"- Retrying test assertion on {course_slug} ({lesson_slug}, {language})."

    if signal_text not in signals:
        signals.append(signal_text)
    sections["Signals"] = signals[-10:]


def _handle_lesson_passed(sections: dict[str, list[str]], payload: dict[str, Any]) -> None:
    """Record a passing submission: persist completion + XP and mark the course done."""
    course_slug = payload.get("course_slug", "")
    lesson_slug = payload.get("lesson_slug", "")
    if not course_slug or not lesson_slug:
        return

    modality = payload.get("modality", "submission")
    signals = sections.setdefault("Signals", [])
    signal_text = f"- Completed {course_slug} ({lesson_slug}) with a passing {modality} submission."
    if signal_text not in signals:
        signals.append(signal_text)
    sections["Signals"] = signals[-10:]

    entry = _load_course_taken(sections, course_slug)
    if lesson_slug not in entry.done:
        entry.done.append(lesson_slug)
        entry.xp += _payload_xp(payload)
    _refresh_course_status(entry, course_slug)
    _write_course_taken(sections, entry)


def _handle_reset(sections: dict[str, list[str]], payload: dict[str, Any]) -> None:
    course_slug = payload.get("course_slug", "")
    lesson_slug = payload.get("lesson_slug", "")
    signals = sections.get("Signals", [])
    signals.append(f"- Reset exercise on {course_slug} ({lesson_slug}) to re-attempt from scratch.")
    sections["Signals"] = signals[-10:]


def _handle_tutor_level_changed(fm: LearnerFrontMatter, payload: dict[str, Any]) -> None:
    style = payload.get("tutor_style")
    if style in ("solveit", "socratic", "direct", "blooms"):
        fm.tutor_style = style
    level = payload.get("understanding_level", "").lower()
    if level in ("beginner", "intermediate", "advanced"):
        fm.understanding_level = level


def _handle_course_authored(sections: dict[str, list[str]], payload: dict[str, Any]) -> None:
    course_slug = payload.get("course_slug", "")
    title = payload.get("title", course_slug)
    count = payload.get("lesson_count", 1)
    built = sections.get("Courses built", [])
    entry = f"- **{course_slug}** — authored '{title}' ({count} Solveit lessons)."
    if entry not in built:
        built.append(entry)
    sections["Courses built"] = built


def _dispatch_learner_event(
    event_type: str,
    fm: LearnerFrontMatter,
    sections: dict[str, list[str]],
    payload: dict[str, Any],
) -> None:
    handlers = {
        "lesson_opened": lambda: _handle_lesson_opened(fm, sections, payload),
        "run_result": lambda: _handle_run_result(sections, payload),
        "reset": lambda: _handle_reset(sections, payload),
        "lesson_passed": lambda: _handle_lesson_passed(sections, payload),
        "tutor_level_changed": lambda: _handle_tutor_level_changed(fm, payload),
        "course_authored": lambda: _handle_course_authored(sections, payload),
    }
    handler = handlers.get(event_type)
    if handler:
        handler()


def _reconstruct_markdown_body(username: str, sections: dict[str, list[str]]) -> str:
    body_parts = [f"# Learning profile — {username}\n"]
    for sec_name, lines in sections.items():
        if sec_name != "Intro":
            body_parts.append(f"## {sec_name}")
            body_parts.append("\n".join(lines).strip())
            body_parts.append("")
    return "\n\n".join(p for p in body_parts if p).strip()


def record_learner_event(
    username: str,
    event_type: str,
    payload: dict[str, Any],
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Records an operational learning event into LEARNING.md."""
    file_path = get_profile_path(username, base_dir)
    if not file_path.is_file():
        get_or_create_profile(username, base_dir)

    raw_text = file_path.read_text(encoding="utf-8")
    fm_raw, body = parse_frontmatter(raw_text)
    fm = LearnerFrontMatter.model_validate(fm_raw)
    fm.updated_at = datetime.now(timezone.utc).isoformat()
    sections = parse_markdown_sections(body)

    _dispatch_learner_event(event_type, fm, sections, payload)

    new_body = _reconstruct_markdown_body(fm.username, sections)
    new_content = f"{serialize_frontmatter(fm)}\n\n{new_body}\n"
    file_path.write_text(new_content, encoding="utf-8")

    return get_or_create_profile(username, base_dir)[1]


def _infer_tutor_style(
    answers: LearnerQuestionnaire,
) -> Literal["solveit", "socratic", "direct", "blooms"]:
    if answers.hint_preference == "guiding_question":
        return "socratic"
    if answers.hint_preference == "direct_explanation":
        return "direct"
    if answers.hint_preference == "toy_example":
        return "solveit"
    return answers.tutor_style


def _infer_modalities(answers: LearnerQuestionnaire) -> list[str]:
    mapping = {
        "diagram": ["drawing", "code"],
        "table": ["spreadsheet", "code"],
        "hands_on": ["code"],
        "story": ["text", "code"],
    }
    if answers.intake_preference and answers.intake_preference in mapping:
        return mapping[answers.intake_preference]
    return answers.preferred_modalities or ["code", "spreadsheet", "drawing"]


def _infer_exercise_format(
    answers: LearnerQuestionnaire,
) -> Literal["micro_steps", "macro_challenges", "guided_completion"]:
    if answers.exercise_format:
        return answers.exercise_format
    if answers.understanding_level == "beginner":
        return "guided_completion"
    return "micro_steps"


def _build_snapshot(
    answers: LearnerQuestionnaire,
    inferred_style: str,
    modalities: list[str],
    inferred_format: str = "micro_steps",
) -> str:
    expl = (
        "concise essentials" if answers.explanation_length == "short" else "in-depth explanations"
    )
    if inferred_format == "guided_completion":
        grain = "guided fill-in-the-blank code completion"
    elif inferred_format == "micro_steps":
        grain = "bite-sized micro-steps"
    else:
        grain = "comprehensive challenges"
    tools = ", ".join(modalities)
    return (
        f"Learner prefers {expl} and practicing through {grain}. "
        f"Primary tools: {tools} with {answers.tone} {inferred_style} guidance at an {answers.pace} pace."
    )


def _build_modality_recommendations(modalities: list[str]) -> list[str]:
    recs: list[str] = []
    mod_set = set(modalities)
    if "spreadsheet" in mod_set:
        recs.append("Offer spreadsheet cell formulas and mental models before coding.")
    if "drawing" in mod_set:
        recs.append("Include visual diagrams, whiteboard sketches, and architecture blueprints.")
    if "code" in mod_set:
        recs.append("Provide hands-on Python/Rust coding exercises with automated micro-tests.")
    if "text" in mod_set:
        recs.append("Provide structured conceptual walkthroughs and Socratic discussions.")
    return recs


def _build_pedagogy_recommendations(
    answers: LearnerQuestionnaire, inferred_format: str = "micro_steps"
) -> list[str]:
    recs: list[str] = []
    if answers.explanation_length == "short":
        recs.append(
            "Keep explanations concise (under 3 sentences); transition rapidly to practice."
        )
    else:
        recs.append(
            "Provide thorough explanations with real-world analogies and conceptual context."
        )

    if inferred_format == "guided_completion":
        recs.append(
            "Provide pre-structured code templates with fill-in-the-blank placeholders (`____`) to eliminate syntax friction."
        )
    elif inferred_format == "micro_steps":
        recs.append(
            "Structure practice into 4-6 small micro-steps with immediate automated assertions."
        )
    else:
        recs.append(
            "Structure practice into 1-2 larger macro challenges with minimal intermediate scaffolding."
        )
    return recs


def _build_tutor_recommendations(tutor_style: str) -> str:
    style_map = {
        "solveit": "Guide using the Solveit method: build intuition with toy data and verified micro-steps.",
        "socratic": "Guide with Socratic inquiry: ask progressive questions before revealing solutions.",
        "direct": "Provide clear, direct explanations with minimal preamble before diving in.",
        "blooms": "Structure exercises along Bloom's taxonomy: from understanding to evaluation and creation.",
    }
    return style_map.get(tutor_style, "Guide using interactive micro-steps.")


def _build_tone_recommendations(tone: str) -> list[str]:
    recs: list[str] = []
    if tone == "pragmatic":
        recs.append(
            "Tone: Pragmatic developer realism — plain-spoken about bugs and computer literalism, zero forced jokes."
        )
    elif tone == "direct":
        recs.append(
            "Tone: Direct technical manual style — neutral, factual, and concise without conversational filler."
        )
    elif tone == "concise":
        recs.append(
            "Tone: Ultra-concise — minimal prose, jump straight into code examples and runnable tasks."
        )
    recs.append(
        "Anti-AI style: Ban 'it is not X, but Y' contrast framing, rhetorical questions, and academic filler ('Crucially', 'In essence')."
    )
    return recs


def _build_all_recommendations(
    tutor_rec: str,
    pedagogy_recs: list[str],
    modality_recs: list[str],
    tone_recs: list[str] | None = None,
) -> str:
    lines = [f"- {tutor_rec}"]
    for item in (tone_recs or []) + pedagogy_recs + modality_recs:
        lines.append(f"- {item}")
    return "\n".join(lines)


def _format_course_list(items: list[str], default_comment: str) -> str:
    if not items:
        return default_comment
    return "\n".join(items)


def aggregate_questionnaire_to_markdown(
    username: str,
    answers: LearnerQuestionnaire,
    existing_taken: list[str] | None = None,
    existing_built: list[str] | None = None,
) -> str:
    """Transforms learner questionnaire responses into a formatted LEARNING.md profile."""
    inferred_style = _infer_tutor_style(answers)
    inferred_mods = _infer_modalities(answers)
    inferred_format = _infer_exercise_format(answers)
    now_iso = datetime.now(timezone.utc).isoformat()
    fm = LearnerFrontMatter(
        username=username,
        updated_at=now_iso,
        version=1,
        preferred_ui=answers.preferred_ui,
        tutor_style=inferred_style,
        tone=answers.tone,
        understanding_level=answers.understanding_level,
        preferred_modalities=inferred_mods,
        pace=answers.pace,
        explanation_length=answers.explanation_length,
        exercise_format=inferred_format,
    )

    snapshot_text = _build_snapshot(answers, inferred_style, inferred_mods, inferred_format)
    tutor_rec = _build_tutor_recommendations(inferred_style)
    modality_recs = _build_modality_recommendations(inferred_mods)
    pedagogy_recs = _build_pedagogy_recommendations(answers, inferred_format)
    tone_recs = _build_tone_recommendations(answers.tone)
    customize_block = _build_all_recommendations(tutor_rec, pedagogy_recs, modality_recs, tone_recs)

    notes_bullet = (
        f"\n- Personal focus: {answers.custom_notes.strip()}"
        if answers.custom_notes.strip()
        else ""
    )

    taken_block = _format_course_list(
        existing_taken or [],
        "<!-- Completed or in-progress courses are recorded here automatically -->",
    )
    built_block = _format_course_list(
        existing_built or [],
        "<!-- Personal courses generated with the Agentic Course Builder are listed here -->",
    )

    fm_yaml = serialize_frontmatter(fm)
    return f"""{fm_yaml}

# Learning profile — {username}

## Snapshot
{snapshot_text}

## Goals & Focus
- {answers.goal.strip()}{notes_bullet}

## Courses taken
{taken_block}

## Courses built
{built_block}

## Signals
- Initialized learning profile from onboarding diagnostic questionnaire.

## Customize next
{customize_block}
"""


def apply_questionnaire_profile(
    username: str,
    answers: LearnerQuestionnaire,
    base_dir: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generates and writes a personalized LEARNING.md file from questionnaire answers."""
    file_path = get_profile_path(username, base_dir)
    existing_taken: list[str] = []
    existing_built: list[str] = []
    if file_path.is_file():
        try:
            _, parsed = get_or_create_profile(username, base_dir)
            existing_taken = parsed.get("courses_taken", [])
            existing_built = parsed.get("courses_built", [])
        except Exception:
            pass

    markdown = aggregate_questionnaire_to_markdown(
        username, answers, existing_taken, existing_built
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(markdown, encoding="utf-8")
    return get_or_create_profile(username, base_dir)


def get_user_progress(username: str, base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return structured per-course progress for a learner (single source: LEARNING.md)."""
    _, parsed = get_or_create_profile(username, base_dir)

    progress: list[dict[str, Any]] = []
    for line in parsed.get("courses_taken", []):
        entry = parse_course_taken_line(line)
        if entry is None:
            continue

        record: dict[str, Any] = {
            "course_slug": entry.course_slug,
            "resume_lesson": entry.last_lesson,
            "completed_lessons": list(entry.done),
            "completed": entry.completed,
            "done_count": len(entry.done),
            "xp": entry.xp,
            "lesson_count": entry.total,
            "resume_order": None,
            "resume_title": None,
        }

        catalog = _course_catalog(entry.course_slug)
        if catalog is not None:
            record["lesson_count"] = len(catalog)
            if entry.last_lesson:
                for slug, order, title in catalog:
                    if slug == entry.last_lesson:
                        record["resume_order"] = order
                        record["resume_title"] = title
                        break

        progress.append(record)
    return progress
