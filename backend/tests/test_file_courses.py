"""
Unit tests for file_courses router and helpers.
"""

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from routers.file_courses import (
    _heading_from_readme,
    _is_safe_subpath,
    _lesson_display_title,
    _normalize_skills,
    _optional_str,
    _unique_lesson_skills,
    _validate_lesson_slug,
    _validate_slug,
    get_course_title,
    get_lesson_path,
    get_lesson_title,
    is_lesson_directory,
    parse_course,
    parse_lesson,
    read_file_content,
)


class TestFileCoursesHelpers:
    """Test pure helper functions in file_courses."""

    def test_get_course_title(self):
        assert get_course_title("tinytorch") == "Tinytorch"
        assert get_course_title("llms-from-scratch") == "Llms From Scratch"
        assert get_course_title("deep_learning_101") == "Deep Learning 101"

    def test_get_lesson_title(self):
        assert get_lesson_title("lesson01", 1) == "Lesson 1: Lesson01"
        assert get_lesson_title("intro-to-tensors", 2) == "Lesson 2: Intro To Tensors"

    def test_read_file_content(self, tmp_path: Path):
        file = tmp_path / "hello.txt"
        file.write_text("Hello World", encoding="utf-8")
        assert read_file_content(file) == "Hello World"
        assert read_file_content(tmp_path / "does_not_exist.txt") == ""

    def test_is_lesson_directory(self, tmp_path: Path):
        assert not is_lesson_directory(tmp_path)

        # Only README.md is not enough
        (tmp_path / "README.md").write_text("# Lesson")
        assert not is_lesson_directory(tmp_path)

        # README + main.py is a lesson
        (tmp_path / "main.py").write_text("print(1)")
        assert is_lesson_directory(tmp_path)

    def test_is_lesson_directory_with_rust_or_metadata(self, tmp_path: Path):
        rust_dir = tmp_path / "rust_lesson"
        rust_dir.mkdir()
        (rust_dir / "README.md").write_text("# Rust")
        (rust_dir / "main.rs").write_text("fn main() {}")
        assert is_lesson_directory(rust_dir)

        meta_dir = tmp_path / "meta_lesson"
        meta_dir.mkdir()
        (meta_dir / "README.md").write_text("# Meta")
        (meta_dir / "metadata.json").write_text('{"exercise_type": "spreadsheet"}')
        assert is_lesson_directory(meta_dir)

    def test_validate_slug(self):
        assert _validate_slug("python-basics") is True
        assert _validate_slug("tinytorch_101") is True
        assert _validate_slug("lesson01") is True

        assert _validate_slug("") is False
        assert _validate_slug("..") is False
        assert _validate_slug("../etc") is False
        assert _validate_slug(".hidden") is False
        assert _validate_slug("a/b") is False
        assert _validate_slug("a\\b") is False
        assert _validate_slug("hello world") is False
        assert _validate_slug("slug;drop table") is False

    def test_validate_lesson_slug(self):
        assert _validate_lesson_slug("lesson01") is True
        assert _validate_lesson_slug("chapter1--lesson01") is True
        assert _validate_lesson_slug("part-a--intro_1") is True

        assert _validate_lesson_slug("") is False
        assert _validate_lesson_slug("--") is False
        assert _validate_lesson_slug("chapter1--") is False
        assert _validate_lesson_slug("--lesson1") is False
        assert _validate_lesson_slug("chapter1--lesson1--extra") is False
        assert _validate_lesson_slug("ch1/../../etc") is False
        assert _validate_lesson_slug("ch1--../bad") is False

    def test_is_safe_subpath(self, tmp_path: Path):
        base = tmp_path / "base"
        base.mkdir()
        child = base / "child"
        child.mkdir()
        nested = child / "deep"
        nested.mkdir()

        assert _is_safe_subpath(child, base) is True
        assert _is_safe_subpath(nested, base) is True

        # Base itself is not a safe subpath of base
        assert _is_safe_subpath(base, base) is False

        # Parent directory is not a safe subpath
        assert _is_safe_subpath(tmp_path, base) is False

        # Outside directory / traversal is not safe
        outside = tmp_path / "outside"
        outside.mkdir()
        assert _is_safe_subpath(outside, base) is False
        traversal = base / ".." / "outside"
        assert _is_safe_subpath(traversal, base) is False


class TestParseLesson:
    """Test parse_lesson function with various directory structures."""

    def test_parse_nonexistent_directory(self, tmp_path: Path):
        assert parse_lesson(tmp_path, "does_not_exist", 1) is None

    def test_parse_directory_missing_readme(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson01"
        lesson_dir.mkdir()
        (lesson_dir / "main.py").write_text("pass")
        assert parse_lesson(tmp_path, "lesson01", 1) is None

    def test_parse_valid_python_lesson(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson01"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Lesson 1 Instructions")
        (lesson_dir / "main.py").write_text("def solve(): pass")
        (lesson_dir / "test.py").write_text("def test_solve(): pass")
        (lesson_dir / "solution.py").write_text("def solve(): return 42")

        lesson = parse_lesson(tmp_path, "lesson01", 1, chapter_slug="chapter1")
        assert lesson is not None
        assert lesson.slug == "chapter1--lesson01"
        assert lesson.title == "Lesson 1 Instructions"
        assert lesson.description == "# Lesson 1 Instructions"
        assert lesson.initial_code == "def solve(): pass"
        assert lesson.test_code == "def test_solve(): pass"
        assert lesson.solution_code == ""
        assert lesson.has_solution is True
        assert lesson.language == "python"
        assert lesson.chapter == "chapter1"
        assert lesson.exercise_type == "code"

    def test_parse_lesson_with_metadata_json(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson_sheet"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Sheet Lesson")
        metadata = {
            "exercise_type": "spreadsheet",
            "google_sheet_id": "sheet_12345",
            "copy_on_open": True,
            "stroke_color": "#00ff00",
            "stroke_width": 6,
        }
        (lesson_dir / "metadata.json").write_text(json.dumps(metadata))

        lesson = parse_lesson(tmp_path, "lesson_sheet", 1)
        assert lesson is not None
        assert lesson.exercise_type == "spreadsheet"
        assert lesson.google_sheet_id == "sheet_12345"
        assert lesson.copy_on_open is True
        assert lesson.stroke_color == "#00ff00"
        assert lesson.stroke_width == 6
        assert lesson.skills == []

    def test_parse_lesson_skills_and_custom_title(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson_skills"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# README heading\n\nBody")
        metadata = {
            "exercise_type": "code",
            "title": "Tensor initialization",
            "skills": ["Tensors", "NumPy", "Tensors", "  ", 12],
        }
        (lesson_dir / "metadata.json").write_text(json.dumps(metadata))

        lesson = parse_lesson(tmp_path, "lesson_skills", 1)
        assert lesson is not None
        assert lesson.title == "Tensor initialization"
        assert lesson.skills == ["Tensors", "NumPy"]
        lesson_dir = tmp_path / "lesson_broken_meta"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Broken Meta")
        (lesson_dir / "metadata.json").write_text("NOT_JSON")

        lesson = parse_lesson(tmp_path, "lesson_broken_meta", 1)
        assert lesson is not None
        assert lesson.exercise_type == "code"
        assert lesson.google_sheet_id is None

    def test_parse_drawing_lesson_with_question_image(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson_draw"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Draw")
        (lesson_dir / "metadata.json").write_text('{"exercise_type": "drawing"}')
        (lesson_dir / "question.png").write_bytes(b"fake_png_data")

        lesson = parse_lesson(tmp_path, "lesson_draw", 1)
        assert lesson is not None
        assert lesson.exercise_type == "drawing"
        assert lesson.image_url == "__image__"

    def test_parse_rust_lesson(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson_rust"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Rust")
        (lesson_dir / "main.rs").write_text("fn main() {}")
        (lesson_dir / "test.rs").write_text("#[test] fn t() {}")
        (lesson_dir / "solution.rs").write_text("fn main() { println!(); }")

        lesson = parse_lesson(tmp_path, "lesson_rust", 1)
        assert lesson is not None
        assert lesson.language == "rust"
        assert lesson.initial_code == "fn main() {}"
        assert lesson.test_code == "#[test] fn t() {}"
        assert lesson.solution_code == ""
        assert lesson.has_solution is True


class TestParseCourse:
    """Test parse_course function."""

    def test_parse_nonexistent_course(self):
        assert parse_course("nonexistent-course-slug-xyz") is None

    def test_parse_course_with_custom_dir(self, tmp_path: Path, monkeypatch):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "mock_course"
        course_dir.mkdir()
        (course_dir / "README.md").write_text("Course description here")

        ch1 = course_dir / "chapter1"
        ch1.mkdir()
        l1 = ch1 / "lesson01"
        l1.mkdir()
        (l1 / "README.md").write_text("# Ch1 L1")
        (l1 / "main.py").write_text("x = 1")

        course = parse_course("mock_course")
        assert course is not None
        assert course.slug == "mock_course"
        assert course.title == "Mock Course"
        assert course.description == "Course description here"
        assert len(course.lessons) == 1
        assert course.lessons[0].slug == "chapter1--lesson01"

    def test_parse_flat_course_without_chapters(self, tmp_path: Path, monkeypatch):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "flat_course"
        course_dir.mkdir()

        l1 = course_dir / "lesson01"
        l1.mkdir()
        (l1 / "README.md").write_text("# Flat L1")
        (l1 / "main.py").write_text("x = 1")

        course = parse_course("flat_course")
        assert course is not None
        assert len(course.lessons) == 1
        assert course.lessons[0].chapter is None
        assert course.skills == []

    def test_parse_course_metadata_title_and_skills(self, tmp_path: Path, monkeypatch):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "skill_course"
        course_dir.mkdir()
        (course_dir / "README.md").write_text("# Ignored heading\nCourse desc")
        (course_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "title": "TinyTorch",
                    "description": "Build a tiny neural net.",
                    "skills": ["Tensors", "NumPy"],
                }
            )
        )
        l1 = course_dir / "lesson01"
        l1.mkdir()
        (l1 / "README.md").write_text("# Tensor init")
        (l1 / "main.py").write_text("x = 1")
        (l1 / "metadata.json").write_text(json.dumps({"skills": ["Tensor init"]}))

        course = parse_course("skill_course")
        assert course is not None
        assert course.title == "TinyTorch"
        assert course.description == "Build a tiny neural net."
        assert course.skills == ["Tensors", "NumPy"]
        assert course.lessons[0].skills == ["Tensor init"]
        assert course.lessons[0].title == "Tensor init"

    def test_parse_course_unions_lesson_skills_when_course_omits_them(
        self, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "union_course"
        course_dir.mkdir()
        l1 = course_dir / "lesson01"
        l1.mkdir()
        (l1 / "README.md").write_text("# One")
        (l1 / "main.py").write_text("x = 1")
        (l1 / "metadata.json").write_text(json.dumps({"skills": ["Alpha", "Beta"]}))
        l2 = course_dir / "lesson02"
        l2.mkdir()
        (l2 / "README.md").write_text("# Two")
        (l2 / "main.py").write_text("x = 2")
        (l2 / "metadata.json").write_text(json.dumps({"skills": ["Beta", "Gamma"]}))

        course = parse_course("union_course")
        assert course is not None
        assert course.skills == ["Alpha", "Beta", "Gamma"]


class TestSkillHelpers:
    def test_normalize_skills(self):
        assert _normalize_skills(None) == []
        assert _normalize_skills("Tensors") == []
        assert _normalize_skills(["Tensors", " ", "NumPy", "Tensors", 3]) == ["Tensors", "NumPy"]
        assert _normalize_skills([f"s{i}" for i in range(20)]) == [f"s{i}" for i in range(12)]

    def test_heading_and_display_title(self):
        assert _heading_from_readme("no heading\n## sub") is None
        assert _heading_from_readme("#  Tensor init  ") == "Tensor init"
        assert _optional_str("  ") is None
        assert _optional_str(12) is None
        assert _lesson_display_title("Custom", "# Heading", "lesson01", 1) == "Custom"
        assert _lesson_display_title(None, "# Heading", "lesson01", 1) == "Heading"
        assert _lesson_display_title(None, "no heading", "lesson01", 1) == "Lesson 1: Lesson01"

    def test_unique_lesson_skills(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson01"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# L")
        (lesson_dir / "main.py").write_text("x = 1")
        (lesson_dir / "metadata.json").write_text(json.dumps({"skills": ["A", "B"]}))
        lesson = parse_lesson(tmp_path, "lesson01", 1)
        assert lesson is not None
        assert _unique_lesson_skills([lesson, lesson]) == ["A", "B"]

        from routers.file_courses import FileLesson

        wide = FileLesson(
            slug="wide",
            title="t",
            description="d",
            initial_code="",
            test_code="",
            order=1,
            skills=[f"s{i}" for i in range(15)],
        )
        assert _unique_lesson_skills([wide]) == [f"s{i}" for i in range(12)]


class TestFileCoursesEndpoints:
    """Integration tests for file_courses API endpoints."""

    def test_list_file_courses(self, client: TestClient):
        response = client.get("/file-courses/")
        assert response.status_code == 200
        courses = response.json()
        assert isinstance(courses, list)
        if courses:
            assert "slug" in courses[0]
            assert "title" in courses[0]
            assert "lesson_count" in courses[0]
            assert "skills" in courses[0]

    def test_get_existing_file_course(self, client: TestClient, auth_headers):
        # List courses to find an existing one
        list_res = client.get("/file-courses/")
        courses = list_res.json()
        if courses:
            slug = courses[0]["slug"]
            res = client.get(f"/file-courses/{slug}", headers=auth_headers)
            assert res.status_code == 200
            data = res.json()
            assert data["slug"] == slug
            assert "lessons" in data

    def test_get_nonexistent_file_course(self, client: TestClient, auth_headers):
        res = client.get("/file-courses/nonexistent-xyz-course", headers=auth_headers)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    def test_get_existing_file_lesson(self, client: TestClient, auth_headers):
        list_res = client.get("/file-courses/")
        courses = list_res.json()
        if courses:
            slug = courses[0]["slug"]
            course_res = client.get(f"/file-courses/{slug}", headers=auth_headers)
            course_data = course_res.json()
            if course_data["lessons"]:
                lesson_slug = course_data["lessons"][0]["slug"]
                lesson_res = client.get(f"/file-courses/{slug}/{lesson_slug}", headers=auth_headers)
                assert lesson_res.status_code == 200
                assert lesson_res.json()["slug"] == lesson_slug

    def test_get_nonexistent_file_lesson(self, client: TestClient, auth_headers):
        list_res = client.get("/file-courses/")
        courses = list_res.json()
        if courses:
            slug = courses[0]["slug"]
            res = client.get(f"/file-courses/{slug}/nonexistent-lesson", headers=auth_headers)
            assert res.status_code == 404
            assert "not found" in res.json()["detail"].lower()

    def test_get_lesson_image_found_and_not_found(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c_img"
        course_dir.mkdir()
        lesson_dir = course_dir / "l_img"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Img")
        (lesson_dir / "question.png").write_bytes(b"fake_image_bytes")

        # Unauthenticated request is rejected (Issue #28)
        unauth = client.get("/file-courses/c_img/l_img/image")
        assert unauth.status_code == 401

        # Found with auth headers
        res = client.get("/file-courses/c_img/l_img/image", headers=auth_headers)
        assert res.status_code == 200
        assert res.content == b"fake_image_bytes"
        assert "private" in res.headers.get("cache-control", "").lower()

        # Found with token query param
        token = auth_headers["Authorization"].split(" ")[1]
        res_token = client.get(f"/file-courses/c_img/l_img/image?token={token}")
        assert res_token.status_code == 200
        assert res_token.content == b"fake_image_bytes"

        # Missing image in existing lesson
        no_img_dir = course_dir / "l_no_img"
        no_img_dir.mkdir()
        (no_img_dir / "README.md").write_text("# No Img")
        res2 = client.get("/file-courses/c_img/l_no_img/image", headers=auth_headers)
        assert res2.status_code == 404

        # Nonexistent lesson
        res3 = client.get("/file-courses/c_img/ghost/image", headers=auth_headers)
        assert res3.status_code == 404

    def test_get_lesson_solution_found_and_not_found(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c_sol"
        course_dir.mkdir()
        lesson_dir = course_dir / "l_sol"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Sol")
        (lesson_dir / "solution.png").write_bytes(b"fake_sol_bytes")

        # Unauthenticated request is rejected (Issue #28)
        unauth = client.get("/file-courses/c_sol/l_sol/solution")
        assert unauth.status_code == 401

        # Found with auth headers
        res = client.get("/file-courses/c_sol/l_sol/solution", headers=auth_headers)
        assert res.status_code == 200
        assert res.content == b"fake_sol_bytes"
        # Must not cache solution images publicly (Issue #28)
        assert "no-store" in res.headers.get("cache-control", "").lower()

        # Found with token query param
        token = auth_headers["Authorization"].split(" ")[1]
        res_token = client.get(f"/file-courses/c_sol/l_sol/solution?token={token}")
        assert res_token.status_code == 200
        assert res_token.content == b"fake_sol_bytes"

        # Missing solution image
        no_sol_dir = course_dir / "l_no_sol"
        no_sol_dir.mkdir()
        (no_sol_dir / "README.md").write_text("# No Sol")
        res2 = client.get("/file-courses/c_sol/l_no_sol/solution", headers=auth_headers)
        assert res2.status_code == 404

        # Nonexistent lesson
        res3 = client.get("/file-courses/c_sol/ghost/solution", headers=auth_headers)
        assert res3.status_code == 404

    def test_path_traversal_attempts_rejected(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        """Path traversal attacks on course_slug and lesson_slug must be rejected (Issue #43)."""
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        # Course slug traversal
        res1 = client.get("/file-courses/..%2F..%2Fetc", headers=auth_headers)
        assert res1.status_code in (400, 404)

        res2 = client.get("/file-courses/%2E%2E", headers=auth_headers)
        assert res2.status_code in (400, 404)

        # Lesson slug traversal
        res3 = client.get("/file-courses/valid_course/..%2F..%2Fetc", headers=auth_headers)
        assert res3.status_code in (400, 404)

        res4 = client.get(
            "/file-courses/valid_course/..%2F..%2Fetc/solution-code", headers=auth_headers
        )
        assert res4.status_code in (400, 404)

        res5 = client.get("/file-courses/valid_course/..%2F..%2Fetc/image", headers=auth_headers)
        assert res5.status_code in (400, 404)

        res6 = client.get("/file-courses/valid_course/..%2F..%2Fetc/solution", headers=auth_headers)
        assert res6.status_code in (400, 404)

        # Direct function calls with traversal return None
        assert parse_course("../../etc") is None
        assert parse_course("..") is None
        assert get_lesson_path("valid_course", "../../etc") is None
        assert get_lesson_path("valid_course", "ch1--../bad") is None

    def test_course_payload_omits_solution_text(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c_secret"
        lesson_dir = course_dir / "l1"
        lesson_dir.mkdir(parents=True)
        (lesson_dir / "README.md").write_text("# L")
        (lesson_dir / "main.py").write_text("pass")
        (lesson_dir / "solution.py").write_text("SECRET_ANSWER = 42\n")

        res = client.get("/file-courses/c_secret", headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        assert "SECRET_ANSWER" not in res.text
        assert body["lessons"][0]["solution_code"] == ""
        assert body["lessons"][0]["has_solution"] is True

    def test_solution_code_requires_auth_and_returns_text(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c_secret"
        lesson_dir = course_dir / "l1"
        lesson_dir.mkdir(parents=True)
        (lesson_dir / "README.md").write_text("# L")
        (lesson_dir / "main.py").write_text("pass")
        (lesson_dir / "solution.py").write_text("SECRET_ANSWER = 42\n")

        denied = client.get("/file-courses/c_secret/l1/solution-code")
        assert denied.status_code == 401

        ok = client.get("/file-courses/c_secret/l1/solution-code", headers=auth_headers)
        assert ok.status_code == 200
        assert ok.json()["solution_code"] == "SECRET_ANSWER = 42\n"

        missing = client.get("/file-courses/c_secret/ghost/solution-code", headers=auth_headers)
        assert missing.status_code == 404

    def test_get_lesson_path_fallback(self, tmp_path: Path, monkeypatch):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c1"
        course_dir.mkdir()
        nested = course_dir / "sub" / "my_lesson"
        nested.mkdir(parents=True)

        found = get_lesson_path("c1", "my_lesson")
        assert found == nested
        assert get_lesson_path("c1", "ghost_lesson") is None

    @patch("routers.file_courses.ai_service.evaluate_drawing")
    def test_submit_drawing_success(
        self, mock_eval, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "draw_course"
        course_dir.mkdir()
        lesson_dir = course_dir / "lesson1"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Draw circle")
        (lesson_dir / "question.png").write_bytes(b"question_png")
        (lesson_dir / "solution.png").write_bytes(b"solution_png")

        mock_eval.return_value = {"passed": True, "message": "Great drawing!"}

        res = client.post(
            "/file-courses/draw_course/lesson1/submit-drawing",
            json={"image_data": "data:image/png;base64,aGVsbG8="},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["passed"] is True
        assert data["message"] == "Great drawing!"

    @patch("routers.file_courses.ai_service.evaluate_drawing")
    def test_submit_drawing_passes_through_rubric(
        self, mock_eval, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "draw_course"
        course_dir.mkdir()
        lesson_dir = course_dir / "lesson1"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Draw layers")
        (lesson_dir / "question.png").write_bytes(b"q")

        mock_eval.return_value = {
            "passed": False,
            "score": 0.4,
            "message": "Intent is right but labels are missing.",
            "checks": [
                {"label": "Intent matches the instructions", "passed": True, "feedback": "Good"},
                {
                    "label": "No missing required elements",
                    "passed": False,
                    "feedback": "Add labels",
                },
                {"label": "No extra or confusing marks", "passed": True, "feedback": "Clean"},
            ],
        }

        res = client.post(
            "/file-courses/draw_course/lesson1/submit-drawing",
            json={"image_data": "aGVsbG8="},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["passed"] is False
        assert data["message"] == "Intent is right but labels are missing."
        assert len(data["checks"]) == 3
        assert data["checks"][1]["label"] == "No missing required elements"
        assert data["checks"][1]["passed"] is False

    def test_submit_drawing_nonexistent_lesson(self, client: TestClient, auth_headers):
        res = client.post(
            "/file-courses/ghost_course/ghost_lesson/submit-drawing",
            json={"image_data": "base64data"},
            headers=auth_headers,
        )
        assert res.status_code == 404

    def test_submit_drawing_missing_question_diagram(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "draw_course"
        course_dir.mkdir()
        lesson_dir = course_dir / "lesson1"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Draw")

        res = client.post(
            "/file-courses/draw_course/lesson1/submit-drawing",
            json={"image_data": "base64data"},
            headers=auth_headers,
        )
        assert res.status_code == 500
        assert "diagram missing" in res.json()["detail"].lower()

    @patch("routers.file_courses.ai_service.evaluate_drawing")
    def test_submit_drawing_ai_error(
        self, mock_eval, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "draw_course"
        course_dir.mkdir()
        lesson_dir = course_dir / "lesson1"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Draw")
        (lesson_dir / "question.png").write_bytes(b"q")

        mock_eval.return_value = {"error": "AI service unavailable"}

        res = client.post(
            "/file-courses/draw_course/lesson1/submit-drawing",
            json={"image_data": "aGVsbG8="},
            headers=auth_headers,
        )
        assert res.status_code == 500
        assert "AI service unavailable" in res.json()["detail"]

    def test_submit_drawing_invalid_base64(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "draw_course"
        course_dir.mkdir()
        lesson_dir = course_dir / "lesson1"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Draw")
        (lesson_dir / "question.png").write_bytes(b"q")

        res = client.post(
            "/file-courses/draw_course/lesson1/submit-drawing",
            json={"image_data": "invalid!!!base64==="},
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "Invalid image data" in res.json()["detail"]

    def test_create_sheet_copy_not_spreadsheet(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c1"
        course_dir.mkdir()
        lesson_dir = course_dir / "l1"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# L1")
        (lesson_dir / "main.py").write_text("x = 1")

        res = client.post(
            "/file-courses/c1/l1/copy-sheet",
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "not a spreadsheet exercise" in res.json()["detail"]

    def test_create_sheet_copy_course_and_lesson_not_found(self, client: TestClient, auth_headers):
        # Course not found
        res = client.post("/file-courses/ghost_course/l1/copy-sheet", headers=auth_headers)
        assert res.status_code == 404

        # Lesson not found
        list_res = client.get("/file-courses/")
        courses = list_res.json()
        if courses:
            slug = courses[0]["slug"]
            res2 = client.post(
                f"/file-courses/{slug}/ghost_lesson/copy-sheet", headers=auth_headers
            )
            assert res2.status_code == 404

    def test_create_sheet_copy_no_service_account(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c_sheet"
        course_dir.mkdir()
        lesson_dir = course_dir / "l_sheet"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Sheet")
        metadata = {"exercise_type": "spreadsheet", "google_sheet_id": "12345"}
        (lesson_dir / "metadata.json").write_text(json.dumps(metadata))

        monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
        monkeypatch.delenv("SERVICE_ACCOUNT_FILE", raising=False)

        res = client.post("/file-courses/c_sheet/l_sheet/copy-sheet", headers=auth_headers)
        assert res.status_code == 501
        assert "Service account file not configured" in res.json()["detail"]

    def test_create_sheet_copy_not_installed(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "c_sheet"
        course_dir.mkdir()
        lesson_dir = course_dir / "l_sheet"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Sheet")
        metadata = {"exercise_type": "spreadsheet", "google_sheet_id": "template_sheet_id"}
        (lesson_dir / "metadata.json").write_text(json.dumps(metadata))

        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/path/to/sa.json")

        res = client.post("/file-courses/c_sheet/l_sheet/copy-sheet", headers=auth_headers)
        # In environment without googleapiclient, it returns 501
        assert res.status_code == 501
        assert "not installed" in res.json()["detail"].lower()


class TestSpreadsheetVerification:
    """Tests for spreadsheet success_cells parsing and the verify-sheet endpoint."""

    def _write_lesson(
        self, tmp_path: Path, monkeypatch, *, exercise_type="spreadsheet", success_cells=None
    ) -> str:
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)
        course_dir = courses_dir / "c_sheet"
        course_dir.mkdir(exist_ok=True)
        lesson_dir = course_dir / "l_sheet"
        lesson_dir.mkdir(exist_ok=True)
        (lesson_dir / "README.md").write_text("# Sheet")
        metadata = {
            "exercise_type": exercise_type,
            "google_sheet_id": "template_sheet_id",
            "success_cells": success_cells or [],
        }
        (lesson_dir / "metadata.json").write_text(json.dumps(metadata))
        return "l_sheet"

    def test_parse_lesson_success_cells_and_hints(self, tmp_path: Path):
        lesson_dir = tmp_path / "lesson_sheet"
        lesson_dir.mkdir()
        (lesson_dir / "README.md").write_text("# Sheet Lesson")
        metadata = {
            "exercise_type": "spreadsheet",
            "google_sheet_id": "sheet_12345",
            "hints": ["First hint", " Second hint ", "First hint", 3],
            "success_cells": [
                {"cell": "b2", "expected": 6},
                {"cell": " C5 ", "expected": "3x3"},
                {"cell": "bad-cell", "expected": "x"},
                {"cell": "D7"},
            ],
        }
        (lesson_dir / "metadata.json").write_text(json.dumps(metadata))

        lesson = parse_lesson(tmp_path, "lesson_sheet", 1)
        assert lesson is not None
        assert lesson.hints == ["First hint", "Second hint"]
        assert [c.model_dump() for c in lesson.success_cells] == [
            {"cell": "B2", "expected": "6"},
            {"cell": "C5", "expected": "3x3"},
        ]

    def test_verify_sheet_requires_auth(self, client: TestClient, tmp_path: Path, monkeypatch):
        self._write_lesson(
            tmp_path,
            monkeypatch,
            success_cells=[{"cell": "B2", "expected": "6"}],
        )
        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet", json={"sheet_id": "sheet_abc123"}
        )
        assert res.status_code == 401

    def test_verify_sheet_not_spreadsheet(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        self._write_lesson(tmp_path, monkeypatch, exercise_type="code")
        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet",
            json={"sheet_id": "sheet_abc123"},
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "not a spreadsheet exercise" in res.json()["detail"]

    def test_verify_sheet_no_success_cells(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        self._write_lesson(tmp_path, monkeypatch)
        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet",
            json={"sheet_id": "sheet_abc123"},
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "success_cells" in res.json()["detail"]

    def test_verify_sheet_invalid_sheet_id(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        self._write_lesson(tmp_path, monkeypatch, success_cells=[{"cell": "B2", "expected": "6"}])
        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet",
            json={"sheet_id": "not a url or id!!!"},
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "Provide a Google Sheets URL" in res.json()["detail"]

    @patch("routers.file_courses.read_user_sheet_values")
    def test_verify_sheet_passed(
        self, mock_read, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        self._write_lesson(
            tmp_path,
            monkeypatch,
            success_cells=[{"cell": "B2", "expected": "6"}, {"cell": "C5", "expected": "3x3"}],
        )
        mock_read.return_value = {"B2": 6.0, "C5": "3x3"}

        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet",
            json={"sheet_id": "https://docs.google.com/spreadsheets/d/student_copy_id/edit"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["passed"] is True
        assert data["verification"] == "ok"
        assert data["checks"][0] == {
            "cell": "B2",
            "expected": "6",
            "actual": "6",
            "ok": True,
        }
        assert all(c["ok"] for c in data["checks"])
        assert "All target cells match" in data["message"]
        mock_read.assert_called_once_with("student_copy_id")

    @patch("routers.file_courses.read_user_sheet_values")
    def test_verify_sheet_failed_reports_cells(
        self, mock_read, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        self._write_lesson(
            tmp_path,
            monkeypatch,
            success_cells=[{"cell": "B2", "expected": "6"}, {"cell": "C5", "expected": "3x3"}],
        )
        mock_read.return_value = {"B2": 5}

        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet",
            json={"sheet_id": "student_copy_id"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["passed"] is False
        assert data["checks"][0]["ok"] is False
        assert data["checks"][0]["actual"] == "5"
        assert data["checks"][1]["ok"] is False
        assert data["checks"][1]["actual"] is None
        assert "2 of 2 target cells did not match" in data["message"]

    @patch("routers.file_courses.read_user_sheet_values")
    def test_verify_sheet_unavailable(
        self, mock_read, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        from spreadsheet_verification import VerificationUnavailableError

        self._write_lesson(tmp_path, monkeypatch, success_cells=[{"cell": "B2", "expected": "6"}])
        mock_read.side_effect = VerificationUnavailableError("verification is not configured")

        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet",
            json={"sheet_id": "student_copy_id"},
            headers=auth_headers,
        )
        assert res.status_code == 501
        assert "not configured" in res.json()["detail"]

    @patch("routers.file_courses.read_user_sheet_values")
    def test_verify_sheet_read_error(
        self, mock_read, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        from spreadsheet_verification import SheetReadError

        self._write_lesson(tmp_path, monkeypatch, success_cells=[{"cell": "B2", "expected": "6"}])
        mock_read.side_effect = SheetReadError("could not read sheet")

        res = client.post(
            "/file-courses/c_sheet/l_sheet/verify-sheet",
            json={"sheet_id": "student_copy_id"},
            headers=auth_headers,
        )
        assert res.status_code == 502
        assert res.json()["detail"] == "could not read sheet"

    def test_grade_sheet_and_value_helpers(self):
        from spreadsheet_verification import (
            SpreadsheetTargetCell,
            extract_sheet_id,
            grade_sheet,
            normalize_cell_reference,
            normalize_sheet_value,
            parse_success_cells,
            values_match,
        )

        assert extract_sheet_id("https://docs.google.com/spreadsheets/d/AbC123-xyz/edit#gid=0") == (
            "AbC123-xyz"
        )
        assert extract_sheet_id("AbC123-xyz_9") == "AbC123-xyz_9"
        assert extract_sheet_id("") is None
        assert extract_sheet_id(123) is None
        assert normalize_cell_reference("  c5 ") == "C5"
        assert normalize_cell_reference("bad-cell") is None
        assert normalize_sheet_value(None) == ""
        assert normalize_sheet_value(6.0) == "6"
        assert values_match("6", 6.0) is True
        assert values_match("3x3", "3X3") is True
        assert values_match("6", "5") is False
        assert parse_success_cells(None) == []
        assert parse_success_cells([{"cell": "B2", "expected": 2}, "junk"]) == [
            SpreadsheetTargetCell(cell="B2", expected="2")
        ]

        cells = parse_success_cells(
            [{"cell": "A1", "expected": "hello"}, {"cell": "B2", "expected": "3"}]
        )
        result = grade_sheet(cells, {"A1": "hello", "B2": 3.0})
        assert result.passed is True
        assert len(result.checks) == 2
        missing = grade_sheet(cells, {"A1": "nope"})
        assert missing.passed is False
        assert missing.checks[1].actual is None


class TestShareExportImport:
    """Tests for Course and Lesson export, sharing, and importing."""

    def test_export_course_bundle(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "exportable"
        course_dir.mkdir()
        (course_dir / "README.md").write_text("# Exportable Course\nA nice course to export.")
        (course_dir / "metadata.json").write_text(
            json.dumps({"title": "Exportable Course", "skills": ["Python", "Math"]})
        )
        lesson_dir = course_dir / "chapter1" / "lesson01"
        lesson_dir.mkdir(parents=True)
        (lesson_dir / "README.md").write_text("# Lesson 1: Basics")
        (lesson_dir / "main.py").write_text("x = 10")
        (lesson_dir / "test.py").write_text("from main import x\nassert x == 10")
        (lesson_dir / "solution.py").write_text("x = 10\n")
        (lesson_dir / "metadata.json").write_text(
            json.dumps({"exercise_type": "code", "skills": ["Basics"]})
        )

        res = client.get("/file-courses/exportable/export", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "course"
        assert data["slug"] == "exportable"
        assert data["title"] == "Exportable Course"
        assert len(data["lessons"]) == 1
        assert data["lessons"][0]["title"] == "Lesson 1: Basics"
        assert data["lessons"][0]["solution_code"] == "x = 10\n"

        # Not found course
        res404 = client.get("/file-courses/ghost_course_xyz/export", headers=auth_headers)
        assert res404.status_code == 404

    def test_export_single_lesson_bundle(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "share_course"
        course_dir.mkdir()
        lesson_dir = course_dir / "chapter1" / "lesson02"
        lesson_dir.mkdir(parents=True)
        (lesson_dir / "README.md").write_text("# Lesson 2: Single Share")
        (lesson_dir / "main.py").write_text("def solve(): return True")
        (lesson_dir / "test.py").write_text("assert True")
        (lesson_dir / "metadata.json").write_text(json.dumps({"exercise_type": "code"}))

        res = client.get(
            "/file-courses/share_course/chapter1--lesson02/export", headers=auth_headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "lesson"
        assert data["course_slug"] == "share_course"
        assert data["lesson"]["title"] == "Lesson 2: Single Share"
        assert data["lesson"]["initial_code"] == "def solve(): return True"

    def test_import_course_bundle(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        payload = {
            "version": 1,
            "kind": "course",
            "slug": "imported-ml",
            "title": "Machine Learning from Scratch",
            "description": "Learn ML basics",
            "skills": ["ML", "Arrays"],
            "lessons": [
                {
                    "title": "Step 1: Vectors",
                    "slug": "lesson01",
                    "chapter": "chapter1",
                    "exercise_type": "code",
                    "language": "python",
                    "description": "# Step 1: Vectors\nWrite a vector.",
                    "initial_code": "vec = []",
                    "test_code": "from main import vec\nassert len(vec) == 2",
                    "solution_code": "vec = [1, 2]",
                    "skills": ["Vectors"],
                }
            ],
        }

        res = client.post("/file-courses/import", json=payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["kind"] == "course"
        assert data["course_slug"] == "imported-ml"
        assert data["lesson_count"] == 1

        # Check files materialized on disk
        target = courses_dir / "imported-ml"
        assert target.is_dir()
        assert (target / "README.md").is_file()
        assert (target / "metadata.json").is_file()
        lesson_file = target / "chapter1" / "lesson01" / "main.py"
        assert lesson_file.is_file()
        assert lesson_file.read_text() == "vec = []"

        # Re-import collision check (should create -imported suffix)
        res_dup = client.post("/file-courses/import", json=payload, headers=auth_headers)
        assert res_dup.status_code == 200
        assert res_dup.json()["course_slug"] == "imported-ml-imported"

    def test_import_single_lesson_standalone_and_into_course(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        # 1. Standalone single lesson
        payload_single = {
            "version": 1,
            "kind": "lesson",
            "lesson": {
                "title": "Solo Challenge",
                "slug": "solo",
                "exercise_type": "code",
                "language": "python",
                "description": "# Solo Challenge",
                "initial_code": "ans = 42",
                "test_code": "assert True",
                "skills": ["Logic"],
            },
        }
        res1 = client.post("/file-courses/import", json=payload_single, headers=auth_headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["kind"] == "lesson"
        assert "shared-" in data1["course_slug"]
        assert (courses_dir / data1["course_slug"] / "chapter1" / "solo" / "main.py").is_file()

        # 2. Import into existing target course
        target_course = courses_dir / "existing_host"
        target_course.mkdir()
        (target_course / "README.md").write_text("# Existing")
        (target_course / "metadata.json").write_text(json.dumps({"title": "Existing"}))

        payload_into_existing = {
            "version": 1,
            "kind": "lesson",
            "target_course_slug": "existing_host",
            "lesson": {
                "title": "Added Challenge",
                "slug": "extra_lesson",
                "chapter": "chapter2",
                "exercise_type": "code",
                "description": "# Extra",
                "initial_code": "extra = True",
                "test_code": "assert True",
            },
        }
        res2 = client.post("/file-courses/import", json=payload_into_existing, headers=auth_headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["course_slug"] == "existing_host"
        assert (target_course / "chapter2" / "extra_lesson" / "main.py").is_file()

        # Bad target course 404
        payload_into_existing["target_course_slug"] = "ghost_host"
        res_bad_host = client.post(
            "/file-courses/import", json=payload_into_existing, headers=auth_headers
        )
        assert res_bad_host.status_code == 404

    def test_import_validation_and_drawing_images(
        self, client: TestClient, auth_headers, tmp_path: Path, monkeypatch
    ):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        # Empty lessons in course bundle fails
        res_empty = client.post(
            "/file-courses/import",
            json={"kind": "course", "title": "Empty", "lessons": []},
            headers=auth_headers,
        )
        assert res_empty.status_code == 400

        # Empty lesson in lesson bundle fails
        res_empty_les = client.post(
            "/file-courses/import",
            json={"kind": "lesson", "lesson": None, "lessons": []},
            headers=auth_headers,
        )
        assert res_empty_les.status_code == 400

        # Drawing lesson with base64 images
        import base64

        sample_b64 = base64.b64encode(b"sample-png-content").decode("ascii")
        drawing_payload = {
            "kind": "course",
            "slug": "drawing-course",
            "title": "Drawing Course",
            "lessons": [
                {
                    "title": "Diagram Task",
                    "slug": "diagram01",
                    "exercise_type": "drawing",
                    "question_image_base64": f"data:image/png;base64,{sample_b64}",
                    "solution_image_base64": sample_b64,
                }
            ],
        }
        res_draw = client.post("/file-courses/import", json=drawing_payload, headers=auth_headers)
        assert res_draw.status_code == 200
        l_dir = courses_dir / "drawing-course" / "chapter1" / "diagram01"
        assert (l_dir / "question.png").is_file()
        assert (l_dir / "question.png").read_bytes() == b"sample-png-content"
        assert (l_dir / "solution.png").is_file()

    def test_helper_unit_functions(self, tmp_path: Path):
        from routers.file_courses import (
            _decode_image_base64_safely,
            _encode_image_file_base64,
            _sanitize_slug,
        )

        assert _sanitize_slug("  Hello World / 123! ") == "hello-world-123"
        assert _sanitize_slug("") == "imported"
        assert _decode_image_base64_safely(None) is None
        assert _decode_image_base64_safely("invalid-b64-%%") is None
        assert _decode_image_base64_safely("aGVsbG8=") == b"hello"

        f = tmp_path / "test.png"
        assert _encode_image_file_base64(f) is None
        f.write_bytes(b"hello")
        assert _encode_image_file_base64(f) == "aGVsbG8="
