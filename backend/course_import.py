"""Trivial "copy-paste from any chat" course import.

Two halves of the no-key course building story:

1. ``build_import_instructions`` produces a short, self-contained prompt that a
   weak consumer model (free Gemini/ChatGPT/Claude tier) can follow to emit a
   good BaseLayer course as a single JSON fenced block.
2. ``import_course`` takes the model's pasted reply, leniently extracts and
   validates the JSON against the lesson schema, verifies every code lesson
   actually runs in the sandbox (solution+tests pass, starter+tests fail), then
   materializes the course through the shared writer used by the agentic path.

No LLM is ever called by this module: the learner runs the prompt in whichever
free chat they like and pastes the reply back.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentic_tools import CuratedCourseResult, CuratedLessonBlueprint
from agentic_workflow import materialize_curated_course
from sandbox_exec import SandboxUnavailableError, execute_in_sandbox, is_docker_daemon_failure

MIN_IMPORT_LESSONS = 4
MAX_IMPORT_LESSONS = 6
MAX_REPLY_CHARS = 150_000
MAX_TOPIC_CHARS = 500
MAX_RESOURCE_CHARS = 6_000
MAX_CODE_FIELD_CHARS = 30_000

# What the BaseLayer sandbox (Docker `sandbox-runner` / Modal) actually installs.
# Everything else must come from the Python standard library. pandas/sklearn/
# requests etc. are NOT safe to assume and make a lesson un-runnable.
INSTALLED_SANDBOX_LIBRARIES = ("numpy", "torch", "matplotlib")
INSTALLED_SANDBOX_LIBRARY_TEXT = ", ".join(INSTALLED_SANDBOX_LIBRARIES)

_REQUIRED_LESSON_FIELDS = (
    "title",
    "objective",
    "toy_data",
    "expected_result",
    "micro_task",
    "inspect_prompt",
    "starter_code",
    "test_code",
    "solution_code",
)

_DEFAULT_CURIOSITY_PROMPT = (
    "What changed between the toy data and the result, and how would you simplify "
    "or extend it in one more step?"
)

_STDLIB_MODULES: frozenset[str] | None = None


def _stdlib_modules() -> frozenset[str]:
    global _STDLIB_MODULES
    if _STDLIB_MODULES is None:
        names = getattr(sys, "stdlib_module_names", None)
        _STDLIB_MODULES = frozenset(names) if names is not None else frozenset()
    return _STDLIB_MODULES


# ---------------------------------------------------------------------------
# Copy-paste instruction prompt
# ---------------------------------------------------------------------------

EXAMPLE_LESSON: dict[str, str] = {
    "title": "Shape: create a 3-element array",
    "objective": "Create a NumPy array of exactly three elements and confirm its shape.",
    "toy_data": "values [1, 2, 3] -> shape (3,)",
    "expected_result": "(3,)",
    "micro_task": "In make_array(), write one line returning np.array([1, 2, 3]).",
    "inspect_prompt": "Run the code. What does the printed shape look like?",
    "starter_code": "import numpy as np\n\ndef make_array():\n    return None\n",
    "test_code": (
        "from main import make_array\nimport numpy as np\n\nassert make_array().shape == (3,)\n"
    ),
    "solution_code": "import numpy as np\n\ndef make_array():\n    return np.array([1, 2, 3])\n",
}


def _example_lesson_block() -> str:
    return json.dumps(EXAMPLE_LESSON, indent=2)


def build_import_instructions(topic: str, resources_text: str = "") -> str:
    """Build the single self-contained copy-paste prompt for ``topic``.

    Self-contained means it embeds the learner's topic, any reference text, the
    sandbox reality (which imports actually work), the Solveit micro-lesson
    contract, one fully worked example lesson, a capped ask (4-6 code-only
    lessons) and a strict output format. It is meant to be usable both as the
    text a human copies into any chat AND as the user/system prompt for a future
    weak-model auto path.
    """
    clean_topic = topic.strip()
    reference_block = ""
    if resources_text.strip():
        clipped = resources_text.strip()[:MAX_RESOURCE_CHARS]
        reference_block = (
            "\nREFERENCE TEXT THE LEARNER PROVIDED (ground your examples in it when useful):\n"
            f"```text\n{clipped}\n```\n"
        )

    return f"""You are writing a course for the BaseLayer learning platform. Build a real, runnable course.

COURSE TO BUILD
Topic: {clean_topic}
{reference_block}
RULES (follow every rule)
1. Write exactly {MIN_IMPORT_LESSONS} to {MAX_IMPORT_LESSONS} Python lessons that teach this topic one tiny step at a time, from simplest to most useful.
2. Every lesson is a Solveit micro-lesson: a tiny toy example with a predicted result, a 1-3 line task, then an inspection question.
3. The learner's code lives in a file named main.py, and your test_code runs right next to it. So test_code MUST start by importing what it checks from main, for example: from main import make_array
4. starter_code must be INCOMPLETE: it must FAIL your tests until the learner finishes the micro_task. solution_code must PASS your tests.
5. Import ONLY the Python standard library plus: {INSTALLED_SANDBOX_LIBRARY_TEXT}. Never import anything else (pandas, sklearn, requests, ... are NOT installed and break the lesson).
6. Keep functions small. No file I/O, no network access, no infinite loops, no input().

OUTPUT FORMAT (strict — do not skip)
Reply ONLY with one ```json fenced block and NOTHING ELSE. No explanations, no text before or after the fence. The block must look EXACTLY like this:

{{
  "title": "Short course title",
  "description": "One sentence on what the learner builds.",
  "narrative_arc": "One sentence on how the lessons build on each other.",
  "lessons": [
    {{
      "title": "Name of this lesson",
      "objective": "The single idea this lesson teaches, in one sentence.",
      "toy_data": "The tiny input to predict on first, e.g. items = [1, 2, 3] -> doubled = [2, 4, 6]",
      "expected_result": "The exact result the toy example must produce.",
      "micro_task": "The concrete 1-3 line task the learner must write.",
      "inspect_prompt": "A question that makes the learner look at their printed output.",
      "starter_code": "Incomplete Python that fails the tests until the task is done (rule 4).",
      "test_code": "Python asserting the toy behavior; imports the learner's function from main.",
      "solution_code": "Short, complete Python that passes test_code."
    }}
  ]
}}

FULLY WORKED EXAMPLE LESSON - copy this exact structure (your lessons may use plain Python or the packages from rule 5):

```json
{_example_lesson_block()}
```

Return the JSON now.
"""


# ---------------------------------------------------------------------------
# Lenient extraction
# ---------------------------------------------------------------------------


class CourseImportError(ValueError):
    """The pasted reply could not produce a valid course (nothing is written)."""


class CourseVerificationError(CourseImportError):
    """Static checks passed but the lessons do not actually run/verify."""


def _first_json_object(text: str) -> dict[str, Any] | None:
    """Return the first balanced top-level JSON object in ``text``."""
    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _strip_json_fence(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def _escape_literal_newlines(text: str) -> str:
    """Repair the most common weak-model JSON mistake.

    Consumer models often emit code fields with *literal* newlines inside the
    JSON string (instead of ``\\n`` escapes), which makes the whole document
    invalid JSON. This state-machine pass converts any raw newline/tab found
    inside a string literal into its escaped form while leaving valid JSON
    untouched (valid JSON never contains raw control characters in strings).
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                out.append(char)
                escaped = False
            elif char == "\\":
                out.append(char)
                escaped = True
            elif char == '"':
                in_string = False
                out.append(char)
            elif char in "\n\r":
                out.append("\\n")
            elif char == "\t":
                out.append("\\t")
            else:
                out.append(char)
        else:
            if char == '"':
                in_string = True
            out.append(char)
    return "".join(out)


def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """If the object is wrapped one level deep, unwrap to the lessons holder."""
    if isinstance(payload.get("lessons"), list):
        return payload
    for _key, value in payload.items():
        if isinstance(value, dict) and isinstance(value.get("lessons"), list):
            merged = dict(value)
            for top_key in ("title", "description", "narrative_arc"):
                if top_key not in merged and isinstance(payload.get(top_key), str):
                    merged[top_key] = payload[top_key]
            return merged
    return payload


def extract_course_payload(reply_text: str) -> dict[str, Any]:
    """Leniently pull the course JSON object out of a messy chat reply."""
    if not reply_text or not reply_text.strip():
        raise CourseImportError(
            "The reply is empty. Paste the model's reply (or upload the .md/.json file) and try again."
        )
    if len(reply_text) > MAX_REPLY_CHARS:
        raise CourseImportError(
            f"The reply is too large (>{MAX_REPLY_CHARS} chars). Import a shorter course."
        )

    cleaned = _strip_json_fence(reply_text)
    payload = _first_json_object(cleaned)
    if payload is None:
        # Weak models often emit raw newlines inside code strings (invalid JSON):
        # retry once with that specific mistake repaired.
        payload = _first_json_object(_escape_literal_newlines(cleaned))
    if payload is None:
        raise CourseImportError(
            "No JSON course found in that reply. The model should reply with one ```json "
            "fenced block; if it added prose or tables around it, paste the whole reply "
            'anyway - but there must be a JSON object with a "lessons" list inside.'
        )
    return _unwrap_payload(payload)


# ---------------------------------------------------------------------------
# Static validation and normalization
# ---------------------------------------------------------------------------


def _clean_code(value: Any) -> str:
    """Trim whitespace and strip one wrapping ```lang fence from a code field."""
    text = value if isinstance(value, str) else ""
    stripped = text.strip()
    fence = re.match(r"^```[a-zA-Z]*\s*\n(.*)\n```$", stripped, re.DOTALL)
    if fence:
        return fence.group(1).strip("\n")
    return stripped


def _required_str(lesson: dict[str, Any], lesson_index: int, field_name: str) -> str:
    value = lesson.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise CourseImportError(
            f'Lesson {lesson_index} is missing a value for "{field_name}". '
            "Ask the model to re-send the course with every required field filled in."
        )
    if (
        field_name in ("starter_code", "test_code", "solution_code")
        and len(value) > MAX_CODE_FIELD_CHARS
    ):
        raise CourseImportError(
            f'Lesson {lesson_index} "{field_name}" is too large '
            f"(>{MAX_CODE_FIELD_CHARS} chars). Keep each code field small."
        )
    return value.strip()


def _import_roots(code: str) -> list[str]:
    """Return the top-level module names this snippet imports."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    roots: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = (alias.name or "").split(".")[0]
                if root:
                    roots.append(root)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                root = node.module.split(".")[0]
                if root:
                    roots.append(root)
    return roots


def _check_imports(lesson: dict[str, Any], lesson_index: int) -> None:
    # "main" is the learner module that sits beside test.py in the sandbox; the
    # rest must come from the standard library or the installed packages.
    allowed = _stdlib_modules() | set(INSTALLED_SANDBOX_LIBRARIES) | {"main"}
    for field_name in ("starter_code", "test_code", "solution_code"):
        code = _clean_code(lesson.get(field_name))
        if not code:
            continue
        for root in _import_roots(code):
            if root not in allowed:
                raise CourseImportError(
                    f"Lesson {lesson_index} ({lesson.get('title', 'untitled')}) imports "
                    f'"{root}", which is not available in the BaseLayer sandbox. '
                    f"Only the Python standard library plus {INSTALLED_SANDBOX_LIBRARY_TEXT} are installed. "
                    "Ask the model to rewrite the lesson without that package."
                )


def _validate_snippets_parse(lesson: dict[str, Any], lesson_index: int) -> None:
    """Reject code that cannot even parse, unless guided blanks (``____``)."""
    for field_name in ("starter_code", "test_code", "solution_code"):
        code = _clean_code(lesson.get(field_name))
        if not code:
            continue
        try:
            ast.parse(code)
        except SyntaxError as exc:
            if field_name == "starter_code" and "____" in code:
                continue
            raise CourseImportError(
                f"Lesson {lesson_index} ({lesson.get('title', 'untitled')}) contains invalid "
                f"Python in {field_name} (line {exc.lineno}: {exc.msg}). Ask the model to fix it."
            ) from exc


def _validate_test_imports_main(lesson: dict[str, Any], lesson_index: int) -> None:
    test_code = _clean_code(lesson.get("test_code"))
    if "from main import" not in test_code and "import main" not in test_code:
        raise CourseImportError(
            f"Lesson {lesson_index} ({lesson.get('title', 'untitled')}) has a test_code that does "
            "not import from main.py, so it never tests the learner's code. Add something like "
            '"from main import my_function" to the test and try again.'
        )


def _normalize_lesson(raw: dict[str, Any], order: int) -> CuratedLessonBlueprint:
    lesson: dict[str, Any] = raw if isinstance(raw, dict) else {}
    cleaned: dict[str, str] = {}
    for field_name in _REQUIRED_LESSON_FIELDS:
        cleaned[field_name] = _required_str(lesson, order, field_name)

    _check_imports(cleaned, order)
    _validate_snippets_parse(cleaned, order)
    _validate_test_imports_main(cleaned, order)

    return CuratedLessonBlueprint(
        title=cleaned["title"],
        order=order,
        modality="code",
        language="python",
        objective=cleaned["objective"],
        toy_data=cleaned["toy_data"],
        expected_result=cleaned["expected_result"],
        micro_task=cleaned["micro_task"],
        inspect_prompt=cleaned["inspect_prompt"],
        curiosity_prompt=(_clean_code(raw.get("curiosity_prompt")) or _DEFAULT_CURIOSITY_PROMPT),
        starter_code=cleaned["starter_code"],
        test_code=cleaned["test_code"],
        solution_code=cleaned["solution_code"],
        source_refs=["Solveit micro-lesson contract (imported from chat)"],
        skills=[],
    )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48].strip("-")


def normalize_course_payload(
    payload: dict[str, Any],
    topic: str = "",
) -> CuratedCourseResult:
    """Validate the extracted JSON and normalize it into the shared course shape.

    Raises :class:`CourseImportError` on any static problem so nothing is written.
    """
    raw_lessons = payload.get("lessons")
    if not isinstance(raw_lessons, list) or not raw_lessons:
        raise CourseImportError(
            'The JSON has no "lessons" list. Ask the model to reply with the exact ```json '
            "structure from the instructions."
        )
    if not MIN_IMPORT_LESSONS <= len(raw_lessons) <= MAX_IMPORT_LESSONS:
        raise CourseImportError(
            f"The course has {len(raw_lessons)} lessons, but a BaseLayer course must have "
            f"exactly {MIN_IMPORT_LESSONS}-{MAX_IMPORT_LESSONS} lessons. Ask the model to match that count."
        )

    title = str(payload.get("title") or topic or "").strip()
    if not title:
        raise CourseImportError(
            'The JSON has no "title" and no topic was provided. Add a title and try again.'
        )
    description = str(payload.get("description") or "").strip()
    narrative_arc = str(payload.get("narrative_arc") or "").strip()

    lessons = [_normalize_lesson(raw, index) for index, raw in enumerate(raw_lessons, start=1)]

    slug_base = _slugify(title) or _slugify(topic) or "course"
    solveit_compliance = {
        "micro_steps_enforced": all(bool(item.micro_task) for item in lessons),
        "toy_data_grounded": all(bool(item.toy_data) for item in lessons),
        "immediate_inspection_present": all(bool(item.inspect_prompt) for item in lessons),
        "curiosity_loop_active": True,
        "boilerplate_eliminated": True,
    }
    grounded_in = ["Solveit micro-lesson contract (imported from a chat reply)"]
    if topic.strip():
        grounded_in.append(f"Learner topic: {topic.strip()}")

    return CuratedCourseResult(
        slug=f"generated-{slug_base}",
        title=title,
        description=description or f"A Solveit micro-step course for {title}.",
        narrative_arc=narrative_arc or "From toy-data intuition to a working implementation.",
        lesson_count=len(lessons),
        lessons=lessons,
        solveit_compliance=solveit_compliance,
        grounded_in=grounded_in,
    )


# ---------------------------------------------------------------------------
# Sandbox verification of the generated lessons
# ---------------------------------------------------------------------------

VerifyStatus = Literal["passed", "failed", "skipped"]


@dataclass
class LessonVerifyRecord:
    order: int
    title: str
    status: VerifyStatus
    solution_passes: bool = False
    starter_fails: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "title": self.title,
            "status": self.status,
            "solution_passes": self.solution_passes,
            "starter_fails": self.starter_fails,
            "detail": self.detail,
        }


def _run_lesson(lesson: CuratedLessonBlueprint, run_solution: bool) -> dict:
    """Execute solution+tests or starter+tests in the platform sandbox."""
    code = lesson.solution_code if run_solution else lesson.starter_code
    return execute_in_sandbox(code, language="python", test_code=lesson.test_code, timeout=8)


def _stderr_snippet(result: dict) -> str:
    stderr = (result.get("stderr") or "").strip()
    if not stderr:
        stdout = (result.get("stdout") or "").strip()
        stderr = stdout or "(no output)"
    return stderr[-400:]


def verify_imported_course(curated: CuratedCourseResult) -> list[LessonVerifyRecord]:
    """Run each code lesson: solution+tests must pass, starter+tests must fail.

    Returns one record per lesson. Raises :class:`CourseVerificationError` on the
    first lesson that fails, with its stderr, so the caller can refuse to publish.
    Propagates :class:`SandboxUnavailableError` when the sandbox cannot run at all.
    """
    records: list[LessonVerifyRecord] = []
    for lesson in curated.lessons:
        solution_result = _run_lesson(lesson, run_solution=True)
        solution_passes = solution_result.get("exit_code") == 0
        if not solution_passes:
            err = _stderr_snippet(solution_result)
            if is_docker_daemon_failure(err):
                raise SandboxUnavailableError(err)
            raise CourseVerificationError(
                f"Lesson {lesson.order} ({lesson.title}) FAILED verification: its solution does "
                f"not pass the tests.\n{err}"
            )

        starter_result = _run_lesson(lesson, run_solution=False)
        starter_fails = starter_result.get("exit_code") != 0
        if not starter_fails:
            raise CourseVerificationError(
                f"Lesson {lesson.order} ({lesson.title}) is pre-solved: the starter code already "
                "passes the tests, so there is nothing left for the learner to do. Ask the model "
                "for an incomplete starter_code."
            )
        records.append(
            LessonVerifyRecord(
                order=lesson.order,
                title=lesson.title,
                status="passed",
                solution_passes=True,
                starter_fails=True,
            )
        )
    return records


# ---------------------------------------------------------------------------
# End-to-end import
# ---------------------------------------------------------------------------


@dataclass
class CourseImportResult:
    slug: str
    title: str
    description: str = ""
    narrative_arc: str = ""
    lesson_count: int = 0
    solveit_compliance: dict[str, bool] = field(default_factory=dict)
    grounded_in: list[str] = field(default_factory=list)
    lesson_verifications: list[LessonVerifyRecord] = field(default_factory=list)
    verified: bool = False


def import_course(
    reply_text: str,
    *,
    topic: str = "",
    courses_dir: Path,
    verify: bool = True,
) -> CourseImportResult:
    """Turn a pasted chat reply into a verified, published BaseLayer course.

    Flow: lenient JSON extraction -> strict static validation -> sandbox
    verification of every code lesson -> materialization via the shared writer.
    Refuses (and writes nothing) when the reply cannot produce a runnable course.
    """
    topic = topic.strip()
    payload = extract_course_payload(reply_text)
    curated = normalize_course_payload(payload, topic=topic)

    verifications: list[LessonVerifyRecord] = []
    if verify:
        # Raises CourseVerificationError / SandboxUnavailableError before any write.
        verifications = verify_imported_course(curated)

    written_path = materialize_curated_course(curated, courses_dir)

    return CourseImportResult(
        slug=written_path.name,
        title=curated.title,
        description=curated.description,
        narrative_arc=curated.narrative_arc,
        lesson_count=curated.lesson_count,
        solveit_compliance=curated.solveit_compliance,
        grounded_in=curated.grounded_in,
        lesson_verifications=verifications,
        verified=verify,
    )
