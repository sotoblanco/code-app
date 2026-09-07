"""Tests for the copy-paste / no-API-key course path:

- ``POST /ai/learning-path/instructions`` (dead-simple prompt builder, no LLM)
- ``POST /ai/learning-path/import`` (lenient parse -> validate -> sandbox verify
  -> materialize via the shared writer)

The sandbox executor is mocked at the module seam (``course_import.execute_in_sandbox``)
so the tests exercise the real parse/validate/write logic without a Docker daemon.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from course_import import (
    CourseImportError,
    build_import_instructions,
    extract_course_payload,
    normalize_course_payload,
)
from routers.file_courses import parse_course
from sandbox_exec import SandboxUnavailableError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_lesson(function_name: str, title: str, objective: str) -> dict:
    return {
        "title": title,
        "objective": objective,
        "toy_data": "a = np.array([1, 2, 3])",
        "expected_result": "an inspected value",
        "micro_task": f"Finish {function_name}() in 1-3 lines.",
        "inspect_prompt": "Run the code. What does the output look like?",
        "starter_code": f"import numpy as np\n\ndef {function_name}(a):\n    return None\n",
        "test_code": (
            f"from main import {function_name}\n"
            "import numpy as np\n"
            "\n"
            f"assert {function_name}(np.array([1, 2, 3])).shape == (3,)\n"
        ),
        "solution_code": (
            f"import numpy as np\n\ndef {function_name}(a):\n    return np.array(a)\n"
        ),
    }


def build_course(lesson_count: int = 4) -> dict:
    lessons = [
        _make_lesson("create_vec", "Create a vector", "Create an array and inspect its shape."),
        _make_lesson("double_vec", "Double a vector", "Apply an element-wise transform."),
        _make_lesson("reshape_vec", "Reshape a vector", "Change a vector's shape."),
        _make_lesson("square_vec", "Square a vector", "Compose an element-wise square."),
        _make_lesson("clip_vec", "Clip a vector", "Bound every value."),
        _make_lesson("dot_vec", "Dot two vectors", "Combine two arrays."),
    ]
    return {
        "title": "NumPy from scratch",
        "description": "Learn NumPy with tiny toy experiments.",
        "narrative_arc": "From creating arrays to composing operations.",
        "lessons": lessons[:lesson_count],
    }


def _fenced(course: dict) -> str:
    return f"```json\n{json.dumps(course)}\n```"


def _make_fake_executor(
    *,
    solutions_pass: bool = True,
    starters_fail: bool = True,
    unavailable: bool = False,
):
    solutions = [lesson["solution_code"] for lesson in build_course()["lessons"]]
    calls: list = []

    def fake(code, language="python", test_code=None, timeout=8):
        calls.append((code, test_code))
        if unavailable:
            raise SandboxUnavailableError("Docker is not running")
        is_solution = any(code.strip() == solution.strip() for solution in solutions)
        if is_solution:
            exit_code = 0 if solutions_pass else 1
            detail = "" if solutions_pass else "AssertionError: expected [1 2 3]"
        else:
            exit_code = 0 if not starters_fail else 1
            detail = "" if starters_fail else "starter already passes"
        return {"stdout": "", "stderr": detail, "exit_code": exit_code}

    fake.calls = calls
    return fake


@pytest.fixture
def courses_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point both COURSES_DIR references at a throwaway dir."""
    target = tmp_path / "courses"
    target.mkdir()
    monkeypatch.setattr("routers.ai.COURSES_DIR", target)
    monkeypatch.setattr("routers.file_courses.COURSES_DIR", target)
    return target


@pytest.fixture
def fake_executor(monkeypatch: pytest.MonkeyPatch):
    def install(fake):
        monkeypatch.setattr("course_import.execute_in_sandbox", fake)
        return fake

    return install


# ---------------------------------------------------------------------------
# Instructions endpoint
# ---------------------------------------------------------------------------


class TestInstructionsEndpoint:
    def test_requires_auth(self, client: TestClient):
        response = client.post(
            "/ai/learning-path/instructions", json={"topic": "numpy broadcasting"}
        )
        assert response.status_code == 401

    def test_returns_a_self_contained_prompt(self, client: TestClient, auth_headers):
        response = client.post(
            "/ai/learning-path/instructions",
            json={"topic": "numpy broadcasting"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        instructions = body["instructions"]
        assert "numpy broadcasting" in instructions
        # sandbox reality is spelled out
        assert "numpy, torch, matplotlib" in instructions
        # Solveit micro-lesson contract
        assert "main.py" in instructions and "from main import" in instructions
        # one fully worked example lesson
        assert "FULLY WORKED EXAMPLE LESSON" in instructions
        assert "make_array" in instructions
        # strict output + lesson cap
        assert "```json" in instructions
        assert "4 to 6" in instructions

    def test_embeds_reference_text(self, client: TestClient, auth_headers):
        response = client.post(
            "/ai/learning-path/instructions",
            json={
                "topic": "pytorch tensors",
                "resources": [
                    {"kind": "paste", "name": "notes", "text": "x = torch.tensor([1, 2])"}
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert "x = torch.tensor([1, 2])" in response.json()["instructions"]
        assert "pytorch tensors" in response.json()["instructions"]

    @pytest.mark.parametrize("topic", ["", "   "])
    def test_empty_topic_is_422(self, client: TestClient, auth_headers, topic):
        response = client.post(
            "/ai/learning-path/instructions", json={"topic": topic}, headers=auth_headers
        )
        assert response.status_code == 422

    def test_instructions_loads_profile_and_includes_traits(self, client: TestClient, auth_headers):
        mocked_profile = {
            "frontmatter": {
                "understanding_level": "advanced",
                "tutor_style": "socratic",
                "explanation_length": "thorough",
                "pace": "sprint",
                "preferred_modalities": ["code", "drawing"],
                "goal": "Master deep learning internals from scratch",
            },
            "snapshot": "Experienced engineer diving into neural network autograd systems.",
        }
        with patch("learner_profile.get_or_create_profile", return_value=("md", mocked_profile)):
            response = client.post(
                "/ai/learning-path/instructions",
                json={"topic": "autograd backward engine"},
                headers=auth_headers,
            )
            assert response.status_code == 200, response.text
            body = response.json()
            instructions = body["instructions"]
            assert "LEARNER PROFILE & ADAPTATION" in instructions
            assert "ADVANCED" in instructions
            assert "SOCRATIC" in instructions
            assert "THOROUGH" in instructions
            assert "SPRINT" in instructions
            assert "code, drawing" in instructions
            assert "Master deep learning internals from scratch" in instructions
            assert (
                "Experienced engineer diving into neural network autograd systems" in instructions
            )
            assert body["personalization"] == {
                "understanding_level": "advanced",
                "tutor_style": "socratic",
                "explanation_length": "thorough",
            }

    def test_instructions_graceful_when_profile_fails(self, client: TestClient, auth_headers):
        with patch(
            "learner_profile.get_or_create_profile",
            side_effect=RuntimeError("Profile store unavailable"),
        ):
            response = client.post(
                "/ai/learning-path/instructions",
                json={"topic": "numpy basics"},
                headers=auth_headers,
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert "numpy basics" in body["instructions"]
            assert body["personalization"] is None


class TestBuildImportInstructions:
    def test_build_instructions_with_beginner_solveit_profile(self):
        profile = {
            "frontmatter": {
                "understanding_level": "beginner",
                "tutor_style": "solveit",
                "explanation_length": "short",
                "pace": "unhurried",
                "preferred_modalities": ["code", "spreadsheet"],
            },
            "snapshot": "New student learning Python data manipulation.",
        }
        prompt = build_import_instructions("pandas vectors", learner_profile=profile)
        assert "LEARNER PROFILE & ADAPTATION" in prompt
        assert "BEGINNER" in prompt
        assert "SOLVEIT METHODOLOGY" in prompt
        assert "CONCISE" in prompt
        assert "UNHURRIED" in prompt
        assert "code, spreadsheet" in prompt
        assert "New student learning Python data manipulation." in prompt
        # Check enhanced prompt rules for weaker models
        assert "Narrative Arc & Progressiveness" in prompt
        assert "Concrete Domain Toy Data" in prompt
        assert "NEVER use lazy generic placeholders" in prompt
        assert "Active Inspection & Prediction" in prompt
        assert "Scaffolded Starter Code" in prompt

    def test_build_instructions_with_advanced_direct_profile(self):
        prompt_direct = build_import_instructions(
            "graph algorithms",
            learner_profile={
                "understanding_level": "advanced",
                "tutor_style": "direct",
                "explanation_length": "short",
            },
        )
        assert "ADVANCED" in prompt_direct
        assert "DIRECT" in prompt_direct
        assert "CONCISE" in prompt_direct

    def test_build_instructions_with_blooms_taxonomy_profile(self):
        prompt_blooms = build_import_instructions(
            "compiler design",
            learner_profile={
                "frontmatter": {
                    "understanding_level": "intermediate",
                    "tutor_style": "blooms",
                    "explanation_length": "thorough",
                }
            },
        )
        assert "INTERMEDIATE" in prompt_blooms
        assert "BLOOM'S TAXONOMY" in prompt_blooms
        assert "THOROUGH" in prompt_blooms

    def test_build_instructions_with_empty_or_none_profile(self):
        prompt_none = build_import_instructions("matrix math", learner_profile=None)
        assert "LEARNER PROFILE & ADAPTATION" not in prompt_none
        assert "Topic: matrix math" in prompt_none

        prompt_empty = build_import_instructions("matrix math", learner_profile={})
        assert "LEARNER PROFILE & ADAPTATION" not in prompt_empty
        assert "Topic: matrix math" in prompt_empty


# ---------------------------------------------------------------------------
# Extraction + normalization unit tests
# ---------------------------------------------------------------------------


class TestExtractAndNormalize:
    def test_clean_fenced_json(self):
        payload = extract_course_payload(_fenced(build_course()))
        assert len(payload["lessons"]) == 4

    def test_messy_prose_with_fence_and_table(self):
        reply = (
            "Here is your course!\n\n"
            "| Lesson | Objective |\n|---|---|\n| Create a vector | ... |\n\n"
            "```json\n"
            f"{json.dumps(build_course())}\n"
            "```\n\nHope this helps!"
        )
        payload = extract_course_payload(reply)
        assert payload["title"] == "NumPy from scratch"

    def test_wrapped_one_level_deep(self):
        reply = f'Here you go: {{"course": {json.dumps(build_course())}}}'
        payload = extract_course_payload(reply)
        assert len(payload["lessons"]) == 4

    def test_raw_newlines_inside_code_strings_are_repaired(self):
        # Consumer models frequently emit literal newlines inside JSON string
        # values (instead of \n escapes), which is invalid JSON. The lenient
        # parser must repair that specific mistake and still import the course.
        course = build_course(lesson_count=1)
        # Turn every escaped \n into a real newline inside the JSON document.
        raw_reply = json.dumps(course).replace("\\n", "\n")
        reply = f"Here is your course!\n\n```json\n{raw_reply}\n```\n\nEnjoy!"
        payload = extract_course_payload(reply)
        assert len(payload["lessons"]) == 1
        lesson = payload["lessons"][0]
        assert lesson["solution_code"].startswith("import numpy as np")
        assert "\n" in lesson["solution_code"]
        assert "\n" in lesson["starter_code"]

    def test_no_json_raises(self):
        with pytest.raises(CourseImportError):
            extract_course_payload("Sorry, I cannot help with that.")

    def test_empty_reply_raises(self):
        with pytest.raises(CourseImportError):
            extract_course_payload("   ")

    def test_too_many_lessons_rejected(self):
        payload = build_course(lesson_count=6)
        payload["lessons"] = payload["lessons"] + [_make_lesson("extra_vec", "Extra", "x")] * 2
        with pytest.raises(CourseImportError, match="4-6"):
            normalize_course_payload(payload)

    def test_missing_field_rejected(self):
        payload = build_course()
        del payload["lessons"][0]["solution_code"]
        with pytest.raises(CourseImportError, match="solution_code"):
            normalize_course_payload(payload)

    def test_unavailable_import_rejected(self):
        payload = build_course()
        payload["lessons"][0]["solution_code"] = (
            "import pandas as pd\n\ndef create_vec(a):\n    return pd.Series(a)\n"
        )
        with pytest.raises(CourseImportError, match="pandas"):
            normalize_course_payload(payload)

    def test_test_code_must_import_main(self):
        payload = build_course()
        payload["lessons"][0]["test_code"] = "assert 1 == 1\n"
        with pytest.raises(CourseImportError, match="from main import"):
            normalize_course_payload(payload)


# ---------------------------------------------------------------------------
# Import endpoint
# ---------------------------------------------------------------------------


class TestImportEndpoint:
    def test_requires_auth(self, client: TestClient):
        response = client.post("/ai/learning-path/import", json={"raw_text": "{}"})
        assert response.status_code == 401

    def test_empty_reply_is_422(self, client: TestClient, auth_headers, courses_dir):
        response = client.post(
            "/ai/learning-path/import",
            json={"topic": "numpy", "raw_text": "   "},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert not list(courses_dir.iterdir())

    def test_clean_fenced_json_imports_and_verifies(
        self, client: TestClient, auth_headers, courses_dir, fake_executor
    ):
        fake = fake_executor(_make_fake_executor())
        response = client.post(
            "/ai/learning-path/import",
            json={
                "topic": "numpy",
                "response_markdown": _fenced(build_course()),
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        # Shaped like the existing BuildCourseResponse
        assert data["slug"].startswith("generated-")
        assert data["title"] == "NumPy from scratch"
        assert data["lesson_count"] == 4
        assert data["verified"] is True
        assert data["solveit_compliance"]["toy_data_grounded"] is True
        assert len(data["lesson_verifications"]) == 4
        assert all(v["status"] == "passed" for v in data["lesson_verifications"])
        assert all(v["solution_passes"] for v in data["lesson_verifications"])
        assert all(v["starter_fails"] for v in data["lesson_verifications"])
        # two sandbox runs per lesson (solution+tests, starter+tests)
        assert len(fake.calls) == 8

        # Real materialized course on disk, readable by the file-course router.
        course_dir = courses_dir / data["slug"]
        assert (course_dir / "README.md").exists()
        assert (course_dir / "chapter1" / "lesson01" / "main.py").exists()
        assert (course_dir / "chapter1" / "lesson01" / "solution.py").exists()
        parsed = parse_course(data["slug"])
        assert parsed is not None
        assert len(parsed.lessons) == 4

    def test_messy_prose_reply_imports(
        self, client: TestClient, auth_headers, courses_dir, fake_executor
    ):
        fake_executor(_make_fake_executor())
        reply = (
            "I'd love to! Here is a great course for you.\n\n"
            "```json\n"
            f"{json.dumps(build_course())}\n"
            "```\n\n"
            "Let me know if you want more lessons on matrix ops!"
        )
        response = client.post(
            "/ai/learning-path/import",
            json={"topic": "numpy", "raw_text": reply},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["lesson_count"] == 4

    def test_raw_text_alias_accepted(
        self, client: TestClient, auth_headers, courses_dir, fake_executor
    ):
        fake_executor(_make_fake_executor())
        response = client.post(
            "/ai/learning-path/import",
            json={"raw_text": json.dumps(build_course())},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["lesson_count"] == 4

    def test_unavailable_package_refuses_and_writes_nothing(
        self, client: TestClient, auth_headers, courses_dir
    ):
        payload = build_course()
        payload["lessons"][0]["solution_code"] = (
            "import requests\n\ndef create_vec(a):\n    return list(a)\n"
        )
        response = client.post(
            "/ai/learning-path/import",
            json={"topic": "numpy", "raw_text": json.dumps(payload)},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "requests" in response.json()["detail"]
        assert not list(courses_dir.iterdir())

    def test_lesson_that_fails_verification_refuses_and_writes_nothing(
        self, client: TestClient, auth_headers, courses_dir, fake_executor
    ):
        fake_executor(_make_fake_executor(solutions_pass=False))
        response = client.post(
            "/ai/learning-path/import",
            json={"topic": "numpy", "raw_text": json.dumps(build_course())},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "FAILED verification" in response.json()["detail"]
        assert not list(courses_dir.iterdir())

    def test_presolved_starter_refuses(self, client, auth_headers, courses_dir, fake_executor):
        fake_executor(_make_fake_executor(starters_fail=False))
        response = client.post(
            "/ai/learning-path/import",
            json={"topic": "numpy", "raw_text": json.dumps(build_course())},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "pre-solved" in response.json()["detail"]
        assert not list(courses_dir.iterdir())

    def test_sandbox_unavailable_returns_503(
        self, client, auth_headers, courses_dir, fake_executor
    ):
        fake_executor(_make_fake_executor(unavailable=True))
        response = client.post(
            "/ai/learning-path/import",
            json={"topic": "numpy", "raw_text": json.dumps(build_course())},
            headers=auth_headers,
        )
        assert response.status_code == 503
        assert "sandbox is unavailable" in response.json()["detail"]
        assert not list(courses_dir.iterdir())

    def test_verify_false_skips_sandbox(self, client, auth_headers, courses_dir, fake_executor):
        called = []

        def fake(*args, **kwargs):
            called.append(args)
            raise AssertionError("sandbox should not be touched when verify=false")

        fake_executor(fake)
        response = client.post(
            "/ai/learning-path/import",
            json={"topic": "numpy", "raw_text": json.dumps(build_course()), "verify": False},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["verified"] is False
        assert data["lesson_verifications"] == []
        assert called == []
        assert (courses_dir / data["slug"]).exists()

    def test_never_calls_the_llm(self, client, auth_headers, courses_dir, fake_executor):
        fake_executor(_make_fake_executor())
        with patch("routers.ai.ai_service.complete", side_effect=AssertionError("no LLM")):
            response = client.post(
                "/ai/learning-path/import",
                json={"topic": "numpy", "raw_text": json.dumps(build_course())},
                headers=auth_headers,
            )
        assert response.status_code == 200, response.text
