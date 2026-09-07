"""
Tests for the 4-step Agentic Course Workflow and Tool Calls:
1. get_learning_intent
2. get_context_learning
3. get_platform_content_tools
4. curate_solveit_course
And end-to-end materialization into BaseLayer.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agentic_tools import (
    curate_solveit_course,
    get_context_learning,
    get_learning_intent,
    get_platform_content_tools,
)
from agentic_workflow import (
    AgenticCourseWorkflow,
    CourseGenerationError,
    materialize_curated_course,
)
from ai_service import AIService
from routers.file_courses import parse_course


def _llm_plan_json(topic: str) -> str:
    """Deterministic fake LLM plan (code-only lessons grounded in numpy)."""
    lesson_specs = [
        (
            "make_vec",
            "import numpy as np\n\ndef make_vec():\n    return np.arange(3)\n",
            "from main import make_vec\nassert make_vec().shape == (3,)\n",
        ),
        (
            "broadcast_add",
            "import numpy as np\n\ndef broadcast_add():\n    return np.arange(3) + 1\n",
            "from main import broadcast_add\nassert broadcast_add().tolist() == [1, 2, 3]\n",
        ),
    ]
    lessons = []
    for i, (name, code, test_code) in enumerate(lesson_specs, start=1):
        lessons.append(
            {
                "title": f"Lesson {i}: {name.replace('_', ' ').title()}",
                "modality": "code",
                "objective": f"Implement {name}() in 1-3 lines.",
                "toy_data": "np.arange(3)",
                "expected_result": "a length-3 array",
                "micro_task": f"Write {name}() so it builds the toy vector.",
                "inspect_prompt": "Run it and print the result's shape.",
                "curiosity_prompt": "How would you vectorize the next step?",
                "starter_code": code,
                "test_code": test_code,
                "solution_code": code,
                "source_refs": ["Platform Sandbox"],
                "skills": ["NumPy", "Shapes"],
            }
        )
    return json.dumps(
        {
            "title": f"{topic} with Solveit",
            "description": "Fake LLM plan for tests.",
            "narrative_arc": "From toy data to verified code.",
            "lessons": lessons,
        }
    )


class TestTool1LearningIntent:
    def test_extracts_concepts_and_goals_from_topic(self, tmp_path: Path):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        course = courses_dir / "tinytorch" / "chapter1" / "lesson02"
        course.mkdir(parents=True)
        (course / "README.md").write_text("NumPy tensors, shapes and arrays.", encoding="utf-8")

        result = get_learning_intent(
            topic="Learn NumPy array shapes and tensor broadcasting",
            materials="Here is a snippet:\n```python\nimport numpy as np\na = np.zeros((2, 3))\n```",
            courses_dir=courses_dir,
        )

        assert "numpy" in [c.lower() for c in result.target_concepts]
        assert len(result.learning_goals) >= 2
        assert len(result.extracted_snippets) >= 1
        assert "np.zeros" in result.extracted_snippets[0]
        assert len(result.related_platform_courses) >= 1


class TestTool2ContextLearning:
    def test_returns_adaptive_default_for_unprofiled_learner(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        result = get_context_learning(username="newbie_coder", data_dir=data_dir)

        assert result.username == "newbie_coder"
        assert result.has_stored_profile is False
        assert "code" in result.preferred_modalities
        assert result.tutor_style == "solveit"
        assert "Solveit micro-step" in result.personalization_guidance

    def test_parses_existing_learning_profile(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        user_dir = data_dir / "learners" / "alex"
        user_dir.mkdir(parents=True)

        profile_content = """---
understanding_level: Advanced
tutor_style: solveit
pace: unhurried
preferred_modalities:
  - spreadsheet
  - drawing
  - code
---

# Learning profile — alex
## Courses taken
- **tinytorch** — chapter 1
"""
        (user_dir / "LEARNING.md").write_text(profile_content, encoding="utf-8")

        result = get_context_learning(username="alex", data_dir=data_dir)

        assert result.has_stored_profile is True
        assert result.understanding_level == "Advanced"
        assert result.pace == "unhurried"
        assert result.tone == "pragmatic"
        assert "spreadsheet" in result.preferred_modalities
        assert "drawing" in result.preferred_modalities
        assert "tinytorch" in result.prior_courses

    def test_parses_tone_and_anti_ai_guidance(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        user_dir = data_dir / "learners" / "dev"
        user_dir.mkdir(parents=True)

        profile_content = """---
understanding_level: Intermediate
tutor_style: solveit
tone: direct
pace: sprint
preferred_modalities:
  - code
---
"""
        (user_dir / "LEARNING.md").write_text(profile_content, encoding="utf-8")
        result = get_context_learning(username="dev", data_dir=data_dir)
        assert result.tone == "direct"
        assert "Direct technical manual style" in result.personalization_guidance
        assert "Ban AI tropes" in result.personalization_guidance

    def test_parses_guided_completion_profile_and_infers_for_beginner(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        user_dir = data_dir / "learners" / "sam"
        user_dir.mkdir(parents=True)

        # Explicit guided_completion
        profile_content = """---
understanding_level: Beginner
tutor_style: solveit
pace: unhurried
exercise_format: guided_completion
preferred_modalities:
  - code
---
"""
        (user_dir / "LEARNING.md").write_text(profile_content, encoding="utf-8")
        result = get_context_learning(username="sam", data_dir=data_dir)
        assert result.exercise_format == "guided_completion"
        assert "Guided Code Completion" in result.personalization_guidance

        # Inferred for beginner when exercise_format is omitted
        user2_dir = data_dir / "learners" / "taylor"
        user2_dir.mkdir(parents=True)
        profile_content_2 = """---
understanding_level: Beginner
tutor_style: solveit
pace: unhurried
preferred_modalities:
  - code
---
"""
        (user2_dir / "LEARNING.md").write_text(profile_content_2, encoding="utf-8")
        result2 = get_context_learning(username="taylor", data_dir=data_dir)
        assert result2.exercise_format == "guided_completion"


class TestTool3PlatformContentTools:
    def test_returns_modalities_and_installed_libraries(self):
        tools = get_platform_content_tools()

        assert "code" in tools.modalities
        assert "spreadsheet" in tools.modalities
        assert "drawing" in tools.modalities

        # Installed sandbox libs
        assert "numpy" in tools.installed_sandbox_libraries
        assert "torch" in tools.installed_sandbox_libraries
        assert "matplotlib" in tools.installed_sandbox_libraries

        # Guidelines
        assert len(tools.pedagogical_guidelines) >= 3


class TestTool4CurateSolveitCourse:
    def test_enforces_solveit_directives_and_validates_python(self):
        raw_lessons = [
            {
                "title": "Minimal Vector",
                "modality": "code",
                "objective": "Create a 3-element vector",
                "toy_data": "[1, 2, 3]",
                "expected_result": "3",
                "micro_task": "Write create_vec() in 1 line",
                "inspect_prompt": "What does len(create_vec()) print?",
                "curiosity_prompt": "Can we vectorize this?",
                "starter_code": "def create_vec():\n    pass\n",
                "test_code": "from main import create_vec\nassert create_vec() == [1, 2, 3]\n",
                "solution_code": "def create_vec():\n    return [1, 2, 3]\n",
            },
            {
                "title": "Spreadsheet Math",
                "modality": "spreadsheet",
                "objective": "Observe matrix doubling",
                "toy_data": "[[1, 2], [3, 4]]",
                "expected_result": "[[2, 4], [6, 8]]",
                "micro_task": "Enter =ARRAYFORMULA(A1:B2 * 2)",
                "inspect_prompt": "Check cell C1",
                "curiosity_prompt": "How does ARRAYFORMULA work?",
                "google_sheet_id": "test_sheet_123",
                "copy_on_open": True,
            },
        ]

        curated = curate_solveit_course(
            course_title="NumPy Primitives",
            course_description="Master primitives in micro-steps.",
            narrative_arc="From scalar toy data to vector operations.",
            lessons=raw_lessons,
        )

        assert curated.slug == "generated-numpy-primitives"
        assert curated.lesson_count == 2
        assert curated.solveit_compliance["micro_steps_enforced"] is True
        assert curated.solveit_compliance["toy_data_grounded"] is True
        assert curated.solveit_compliance["immediate_inspection_present"] is True
        assert curated.solveit_compliance["curiosity_loop_active"] is True
        assert curated.lessons[0].modality == "code"
        assert curated.lessons[1].modality == "spreadsheet"

    def test_curate_solveit_course_preserves_guided_blank_templates(self):
        # Guided completion blank templates with ____ syntax
        raw_lessons = [
            {
                "title": "Fill the Tensor Creation Blank",
                "modality": "code",
                "objective": "Fill in the blank to return [10, 20, 30]",
                "toy_data": "[10, 20, 30]",
                "expected_result": "[10, 20, 30]",
                "micro_task": "Replace ____ with 10 and 30",
                "inspect_prompt": "Run to check the array values",
                "curiosity_prompt": "How does this compare to list literals?",
                "starter_code": "def make_list():\n    return [____, 20, ____]\n",
                "test_code": "from main import make_list\nassert make_list() == [10, 20, 30]\n",
                "solution_code": "def make_list():\n    return [10, 20, 30]\n",
            }
        ]
        curated = curate_solveit_course(
            course_title="Guided List Basics",
            course_description="Guided fill-in-the-blank practice.",
            narrative_arc="Scaffolded learning.",
            lessons=raw_lessons,
        )
        assert len(curated.lessons) == 1
        assert "____" in curated.lessons[0].starter_code


class TestAgenticWorkflowExecution:
    def test_end_to_end_agentic_workflow_records_all_traces_and_materializes(
        self, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        workflow = AgenticCourseWorkflow(
            courses_dir=courses_dir,
            data_dir=tmp_path / "data",
            generate_text=lambda prompt: _llm_plan_json("Tensor Math and Broadcasting"),
        )
        result = workflow.execute(
            topic="Tensor Math and Broadcasting",
            materials="import numpy as np\na = np.array([1, 2])",
            username="alex",
        )

        # Verify all 4 required tool calls are tracked in tool_traces
        trace_names = [t.tool_name for t in result.tool_traces]
        assert "get_learning_intent" in trace_names
        assert "get_context_learning" in trace_names
        assert "get_platform_content_tools" in trace_names
        assert "curate_solveit_course" in trace_names
        assert "materialize_course" in trace_names

        # Verify filesystem course matches BaseLayer course structure
        course_dir = courses_dir / result.slug
        assert (course_dir / "README.md").is_file()
        assert (course_dir / "chapter1" / "lesson01" / "README.md").is_file()
        assert (course_dir / "chapter1" / "lesson01" / "metadata.json").is_file()
        assert (course_dir / "metadata.json").is_file()

        lesson_meta = json.loads(
            (course_dir / "chapter1" / "lesson01" / "metadata.json").read_text()
        )
        course_meta = json.loads((course_dir / "metadata.json").read_text())
        assert "skills" in lesson_meta
        assert course_meta.get("title")
        assert isinstance(course_meta.get("skills"), list)

        # Check that parse_course in file_courses router parses it successfully!
        parsed = parse_course(result.slug)
        assert parsed is not None
        assert parsed.slug == result.slug
        assert len(parsed.lessons) == result.lesson_count
        assert parsed.lessons[0].slug.startswith("chapter1--lesson")

    def test_end_to_end_course_never_contains_toy_or_unowned_assets(self, tmp_path, monkeypatch):
        """Published generated courses must not contain the Google sample sheet id,
        blank drawing placeholders, or spreadsheet/drawing exercise types."""
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        workflow = AgenticCourseWorkflow(
            courses_dir=courses_dir,
            data_dir=tmp_path / "data",
            generate_text=lambda prompt: _llm_plan_json("NumPy broadcasting"),
        )
        result = workflow.execute(
            topic="NumPy broadcasting and matrix multiplication",
            materials="",
            username="alex",
        )

        sample_sheet_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        course_dir = courses_dir / result.slug
        for text_file in course_dir.rglob("*.py"):
            assert sample_sheet_id not in text_file.read_text(encoding="utf-8")
        for metadata_file in course_dir.rglob("metadata.json"):
            meta = json.loads(metadata_file.read_text(encoding="utf-8"))
            if "exercise_type" in meta:  # lesson-level metadata
                assert meta["exercise_type"] == "code"
            assert "google_sheet_id" not in meta
        assert not list(course_dir.rglob("question.png"))

    def test_materialize_refuses_spreadsheet_and_drawing_lessons(self, tmp_path):
        """Even a curated set containing a spreadsheet/drawing lesson (e.g. one
        carrying Google's public sample sheet id) is refused and never written."""
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()

        code_lesson = {
            "title": "Toy Code",
            "modality": "code",
            "objective": "obj",
            "toy_data": "[1, 2, 3]",
            "expected_result": "3",
            "micro_task": "task",
            "inspect_prompt": "inspect",
            "curiosity_prompt": "curiosity",
            "starter_code": "def f():\n    return [1, 2, 3]\n",
            "test_code": "from main import f\nassert f() == [1, 2, 3]\n",
            "solution_code": "def f():\n    return [1, 2, 3]\n",
        }
        spreadsheet_lesson = {
            **code_lesson,
            "title": "Sheets Toy",
            "modality": "spreadsheet",
            "google_sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "copy_on_open": True,
        }
        drawing_lesson = {
            **code_lesson,
            "title": "Drawing Toy",
            "modality": "drawing",
            "question_image_desc": "A diagram",
        }

        curated = curate_solveit_course(
            course_title="Toy mixed course",
            course_description="desc",
            narrative_arc="arc",
            lessons=[code_lesson, spreadsheet_lesson],
        )
        with pytest.raises(CourseGenerationError, match="spreadsheet"):
            materialize_curated_course(curated, courses_dir)
        assert list(courses_dir.iterdir()) == []

        curated_drawing = curate_solveit_course(
            course_title="Toy drawing course",
            course_description="desc",
            narrative_arc="arc",
            lessons=[drawing_lesson],
        )
        with pytest.raises(CourseGenerationError, match="drawing"):
            materialize_curated_course(curated_drawing, courses_dir)
        assert list(courses_dir.iterdir()) == []

    def test_workflow_refuses_to_publish_when_no_llm_configured(self, tmp_path):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()

        workflow = AgenticCourseWorkflow(courses_dir=courses_dir, data_dir=tmp_path / "data")
        with pytest.raises(CourseGenerationError) as excinfo:
            workflow.execute(
                topic="NumPy broadcasting and matrix multiplication",
                materials="",
                username="alex",
            )

        assert "No AI model is configured" in str(excinfo.value)
        assert list(courses_dir.iterdir()) == []

    def test_workflow_refuses_to_publish_when_llm_returns_no_lessons(self, tmp_path):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()

        workflow = AgenticCourseWorkflow(
            courses_dir=courses_dir,
            data_dir=tmp_path / "data",
            generate_text=lambda prompt: "",
        )
        with pytest.raises(CourseGenerationError) as excinfo:
            workflow.execute(topic="NumPy broadcasting", materials="", username="alex")

        assert "no usable lessons" in str(excinfo.value)
        assert list(courses_dir.iterdir()) == []

    def test_workflow_refuses_to_publish_when_llm_raises(self, tmp_path):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()

        def boom(prompt):
            raise RuntimeError("provider is down")

        workflow = AgenticCourseWorkflow(
            courses_dir=courses_dir,
            data_dir=tmp_path / "data",
            generate_text=boom,
        )
        with pytest.raises(CourseGenerationError) as excinfo:
            workflow.execute(topic="NumPy broadcasting", materials="", username="alex")

        assert "provider is down" in str(excinfo.value)
        assert list(courses_dir.iterdir()) == []

    def test_workflow_refuses_non_code_lessons_from_llm(self, tmp_path):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()

        bad_plan = json.dumps(
            {
                "title": "Bad",
                "description": "bad",
                "narrative_arc": "bad",
                "lessons": [
                    {
                        "title": "Sheets magic",
                        "modality": "spreadsheet",
                        "objective": "obj",
                        "toy_data": "cells",
                        "expected_result": "1",
                        "micro_task": "task",
                        "inspect_prompt": "inspect",
                        "curiosity_prompt": "curiosity",
                    }
                ],
            }
        )
        workflow = AgenticCourseWorkflow(
            courses_dir=courses_dir,
            data_dir=tmp_path / "data",
            generate_text=lambda prompt: bad_plan,
        )
        with pytest.raises(CourseGenerationError, match="assets"):
            workflow.execute(topic="NumPy broadcasting", materials="", username="alex")

        assert list(courses_dir.iterdir()) == []

    def test_fastapi_build_endpoint_uses_agentic_workflow(
        self, client, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)
        monkeypatch.setattr(AIService, "is_configured", property(lambda self: True))
        monkeypatch.setattr(
            AIService, "complete", lambda self, prompt: _llm_plan_json("vector calculus")
        )

        with patch("routers.ai.COURSES_DIR", courses_dir):
            response = client.post(
                "/ai/learning-path/build",
                json={
                    "topic": "Vector Calculus and Gradient Steps",
                    "resources": [{"kind": "paste", "name": "notes", "text": "grad = [0.1, 0.2]"}],
                },
                headers=auth_headers,
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["slug"].startswith("generated-")
        assert data["lesson_count"] >= 2
        assert "tool_traces" in data
        assert len(data["tool_traces"]) >= 4
        tools_called = [t["tool_name"] for t in data["tool_traces"]]
        assert "get_learning_intent" in tools_called
        assert "get_context_learning" in tools_called
        assert "get_platform_content_tools" in tools_called
        assert "curate_solveit_course" in tools_called

    def test_fastapi_build_endpoint_refuses_and_writes_nothing_when_llm_down(
        self, client, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)
        monkeypatch.setattr(AIService, "is_configured", property(lambda self: False))

        with patch("routers.ai.COURSES_DIR", courses_dir):
            response = client.post(
                "/ai/learning-path/build",
                json={
                    "topic": "NumPy broadcasting and matrix multiplication",
                    "resources": [],
                },
                headers=auth_headers,
            )

        assert response.status_code == 503, response.text
        detail = response.json()["detail"]
        assert "No AI model is configured" in detail
        assert "NumPy broadcasting" in detail
        # Nothing may be published as a fake course on the homepage.
        assert list(courses_dir.iterdir()) == []
