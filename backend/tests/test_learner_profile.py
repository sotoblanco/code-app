"""
Tests for LEARNING.md Learner Profile Management & Event Recording (Issue #23).
"""

from pathlib import Path
from unittest.mock import patch

from learner_profile import (
    LearnerQuestionnaire,
    aggregate_questionnaire_to_markdown,
    apply_questionnaire_profile,
    get_or_create_profile,
    get_user_progress,
    parse_frontmatter,
    record_learner_event,
    update_profile_markdown,
)


class TestLearnerProfileManager:
    def test_creates_default_profile_on_first_access(self, tmp_path: Path):
        content, parsed = get_or_create_profile("test_user", base_dir=tmp_path)

        assert "username: test_user" in content
        assert "preferred_ui: light" in content
        assert "tutor_style: solveit" in content
        assert parsed["frontmatter"]["username"] == "test_user"
        assert parsed["frontmatter"]["understanding_level"] == "intermediate"
        assert (tmp_path / "test_user" / "LEARNING.md").is_file()

    def test_parse_frontmatter_and_sections(self):
        sample = """---
username: alex
updated_at: 2026-09-05T18:00:00Z
version: 1
preferred_ui: classic
tutor_style: socratic
understanding_level: advanced
preferred_modalities:
  - spreadsheet
  - code
pace: sprint
---

# Learning profile — alex

## Snapshot
Custom snapshot text.

## Courses taken
- **tinytorch** — lesson 01 (completed).
"""
        fm, body = parse_frontmatter(sample)
        assert fm["username"] == "alex"
        assert fm["preferred_ui"] == "classic"
        assert fm["tutor_style"] == "socratic"
        assert fm["understanding_level"] == "advanced"
        assert fm["preferred_modalities"] == ["spreadsheet", "code"]
        assert fm["pace"] == "sprint"
        assert "Snapshot" in body

    def test_update_profile_markdown_validates_and_saves(self, tmp_path: Path):
        get_or_create_profile("editor_user", base_dir=tmp_path)

        updated_md = """---
username: editor_user
updated_at: 2026-09-05T19:00:00Z
version: 1
preferred_ui: light
tutor_style: solveit
understanding_level: beginner
preferred_modalities:
  - code
  - drawing
pace: unhurried
---

# Learning profile — editor_user

## Snapshot
I prefer visual and drawing warm-ups before jumping to code.

## Courses taken

## Courses built

## Signals

## Customize next
"""
        content, parsed = update_profile_markdown("editor_user", updated_md, base_dir=tmp_path)
        assert parsed["frontmatter"]["understanding_level"] == "beginner"
        assert parsed["frontmatter"]["preferred_modalities"] == ["code", "drawing"]
        assert "visual and drawing warm-ups" in parsed["snapshot"]

    def test_record_lesson_opened_event(self, tmp_path: Path):
        get_or_create_profile("student1", base_dir=tmp_path)

        parsed = record_learner_event(
            username="student1",
            event_type="lesson_opened",
            payload={
                "course_slug": "tinytorch",
                "lesson_slug": "chapter1--lesson02",
                "ui": "light",
            },
            base_dir=tmp_path,
        )

        assert parsed["frontmatter"]["preferred_ui"] == "light"
        assert any(
            "tinytorch" in line and "chapter1--lesson02" in line for line in parsed["courses_taken"]
        )

    def test_record_run_and_retry_signals(self, tmp_path: Path):
        get_or_create_profile("coder1", base_dir=tmp_path)

        # Failed submit records struggle/retry signal
        record_learner_event(
            username="coder1",
            event_type="run_result",
            payload={
                "course_slug": "tinytorch",
                "lesson_slug": "lesson02",
                "success": False,
                "is_submit": True,
                "language": "python",
            },
            base_dir=tmp_path,
        )

        _, parsed = get_or_create_profile("coder1", base_dir=tmp_path)
        assert any("Retrying test assertion" in s and "tinytorch" in s for s in parsed["signals"])

        # Successful submit records completion signal
        record_learner_event(
            username="coder1",
            event_type="run_result",
            payload={
                "course_slug": "tinytorch",
                "lesson_slug": "lesson02",
                "success": True,
                "is_submit": True,
                "language": "python",
            },
            base_dir=tmp_path,
        )

        _, parsed2 = get_or_create_profile("coder1", base_dir=tmp_path)
        assert any("Completed tinytorch" in s for s in parsed2["signals"])

    def test_record_lesson_passed_event(self, tmp_path: Path):
        get_or_create_profile("drawer1", base_dir=tmp_path)

        record_learner_event(
            username="drawer1",
            event_type="lesson_passed",
            payload={
                "course_slug": "tinytorch",
                "lesson_slug": "chapter1--lesson10",
                "modality": "drawing",
            },
            base_dir=tmp_path,
        )

        _, parsed = get_or_create_profile("drawer1", base_dir=tmp_path)
        assert any(
            "Completed tinytorch" in s and "chapter1--lesson10" in s and "drawing" in s
            for s in parsed["signals"]
        )

    def test_record_course_authored_event(self, tmp_path: Path):
        get_or_create_profile("author1", base_dir=tmp_path)

        record_learner_event(
            username="author1",
            event_type="course_authored",
            payload={
                "course_slug": "generated-numpy-intro",
                "title": "NumPy Intro",
                "lesson_count": 4,
            },
            base_dir=tmp_path,
        )

        _, parsed = get_or_create_profile("author1", base_dir=tmp_path)
        assert any(
            "generated-numpy-intro" in b and "4 Solveit lessons" in b
            for b in parsed["courses_built"]
        )

    def test_record_tutor_level_changed_event(self, tmp_path: Path):
        get_or_create_profile("tutor_user", base_dir=tmp_path)

        record_learner_event(
            username="tutor_user",
            event_type="tutor_level_changed",
            payload={"tutor_style": "socratic", "understanding_level": "advanced"},
            base_dir=tmp_path,
        )

        _, parsed = get_or_create_profile("tutor_user", base_dir=tmp_path)
        assert parsed["frontmatter"]["tutor_style"] == "socratic"
        assert parsed["frontmatter"]["understanding_level"] == "advanced"

    def test_lesson_opened_tracks_last_lesson_per_course(self, tmp_path: Path):
        get_or_create_profile("resumer", base_dir=tmp_path)

        record_learner_event(
            username="resumer",
            event_type="lesson_opened",
            payload={
                "course_slug": "tinytorch",
                "lesson_slug": "chapter1--lesson01",
                "ui": "light",
            },
            base_dir=tmp_path,
        )
        record_learner_event(
            username="resumer",
            event_type="lesson_opened",
            payload={
                "course_slug": "tinytorch",
                "lesson_slug": "chapter2--lesson02",
                "ui": "light",
            },
            base_dir=tmp_path,
        )
        record_learner_event(
            username="resumer",
            event_type="lesson_opened",
            payload={"course_slug": "llms-from-scratch", "lesson_slug": "lesson03", "ui": "light"},
            base_dir=tmp_path,
        )

        progress = {p["course_slug"]: p for p in get_user_progress("resumer", base_dir=tmp_path)}
        assert progress["tinytorch"]["resume_lesson"] == "chapter2--lesson02"
        assert progress["llms-from-scratch"]["resume_lesson"] == "lesson03"

    def test_lesson_passed_persists_completion_and_xp_idempotently(self, tmp_path: Path):
        get_or_create_profile("finisher", base_dir=tmp_path)

        def pass_lesson(xp: int):
            record_learner_event(
                username="finisher",
                event_type="lesson_passed",
                payload={
                    "course_slug": "tinytorch",
                    "lesson_slug": "chapter1--lesson01",
                    "modality": "code",
                    "xp": xp,
                },
                base_dir=tmp_path,
            )
            return get_user_progress("finisher", base_dir=tmp_path)[0]

        first = pass_lesson(25)
        assert first["done_count"] == 1
        assert first["completed_lessons"] == ["chapter1--lesson01"]
        assert first["xp"] == 25

        # Re-passing the same lesson must not double-count completion or XP.
        second = pass_lesson(40)
        assert second["done_count"] == 1
        assert second["completed_lessons"] == ["chapter1--lesson01"]
        assert second["xp"] == 25

    def test_passing_last_lesson_marks_course_complete(self, tmp_path: Path, monkeypatch):
        courses_dir = tmp_path / "courses"
        courses_dir.mkdir()
        monkeypatch.setattr("routers.file_courses.COURSES_DIR", courses_dir)

        course_dir = courses_dir / "tiny"
        chapter_dir = course_dir / "chapter1"
        chapter_dir.mkdir(parents=True)
        for name in ("lesson01", "lesson02"):
            lesson_dir = chapter_dir / name
            lesson_dir.mkdir()
            (lesson_dir / "README.md").write_text(f"# {name}")
            (lesson_dir / "main.py").write_text("x = 1")

        get_or_create_profile("completer", base_dir=tmp_path)

        def progress() -> dict:
            return get_user_progress("completer", base_dir=tmp_path)[0]

        record_learner_event(
            username="completer",
            event_type="lesson_opened",
            payload={"course_slug": "tiny", "lesson_slug": "chapter1--lesson01", "ui": "light"},
            base_dir=tmp_path,
        )
        record_learner_event(
            username="completer",
            event_type="lesson_passed",
            payload={
                "course_slug": "tiny",
                "lesson_slug": "chapter1--lesson01",
                "modality": "code",
                "xp": 30,
            },
            base_dir=tmp_path,
        )
        assert progress()["completed"] is False

        record_learner_event(
            username="completer",
            event_type="lesson_passed",
            payload={
                "course_slug": "tiny",
                "lesson_slug": "chapter1--lesson02",
                "modality": "code",
                "xp": 35,
            },
            base_dir=tmp_path,
        )
        final = progress()
        assert final["completed"] is True
        assert final["done_count"] == final["lesson_count"] == 2
        assert final["xp"] == 65

        # Reopening a lesson of a completed course keeps it completed.
        record_learner_event(
            username="completer",
            event_type="lesson_opened",
            payload={"course_slug": "tiny", "lesson_slug": "chapter1--lesson01", "ui": "classic"},
            base_dir=tmp_path,
        )
        assert progress()["completed"] is True

    def test_progress_is_isolated_per_user(self, tmp_path: Path):
        get_or_create_profile("alice", base_dir=tmp_path)
        get_or_create_profile("bob", base_dir=tmp_path)

        record_learner_event(
            username="alice",
            event_type="lesson_opened",
            payload={"course_slug": "tinytorch", "lesson_slug": "lesson01", "ui": "light"},
            base_dir=tmp_path,
        )

        alice = {p["course_slug"] for p in get_user_progress("alice", base_dir=tmp_path)}
        bob = get_user_progress("bob", base_dir=tmp_path)
        assert "tinytorch" in alice
        assert bob == []


class TestLearnerProfileAPI:
    def test_get_learning_profile_requires_auth(self, client):
        response = client.get("/me/learning-profile")
        assert response.status_code == 401

    def test_get_learning_profile_authenticated(self, client, auth_headers, tmp_path: Path):
        with patch("learner_profile.get_learners_data_dir", return_value=tmp_path):
            response = client.get("/me/learning-profile", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "markdown" in data
        assert "parsed" in data
        assert data["parsed"]["frontmatter"]["username"] == "testuser"

    def test_put_learning_profile_authenticated(self, client, auth_headers, tmp_path: Path):
        valid_md = """---
username: testuser
updated_at: 2026-09-05T20:00:00Z
version: 1
preferred_ui: light
tutor_style: solveit
understanding_level: advanced
preferred_modalities:
  - code
pace: sprint
---

# Learning profile — testuser

## Snapshot
Advanced test runner.
"""
        with patch("learner_profile.get_learners_data_dir", return_value=tmp_path):
            response = client.put(
                "/me/learning-profile",
                json={"markdown": valid_md},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["frontmatter"]["understanding_level"] == "advanced"
        assert data["parsed"]["frontmatter"]["pace"] == "sprint"

    def test_post_event_authenticated(self, client, auth_headers, tmp_path: Path):
        with patch("learner_profile.get_learners_data_dir", return_value=tmp_path):
            response = client.post(
                "/me/learning-profile/events",
                json={
                    "event_type": "reset",
                    "payload": {"course_slug": "tinytorch", "lesson_slug": "lesson01"},
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["success"] is True
        signals = response.json()["profile"]["signals"]
        assert any("Reset exercise on tinytorch" in s for s in signals)

    def test_get_progress_requires_auth(self, client):
        response = client.get("/me/progress")
        assert response.status_code == 401

    def test_get_progress_returns_resume_and_completions(self, client, auth_headers):
        event = client.post(
            "/me/learning-profile/events",
            json={
                "event_type": "lesson_opened",
                "payload": {
                    "course_slug": "tinytorch",
                    "lesson_slug": "chapter1--lesson02",
                    "ui": "light",
                },
            },
            headers=auth_headers,
        )
        assert event.status_code == 200

        passed = client.post(
            "/me/learning-profile/events",
            json={
                "event_type": "lesson_passed",
                "payload": {
                    "course_slug": "tinytorch",
                    "lesson_slug": "chapter1--lesson01",
                    "modality": "code",
                    "xp": 25,
                },
            },
            headers=auth_headers,
        )
        assert passed.status_code == 200

        response = client.get("/me/progress", headers=auth_headers)
        assert response.status_code == 200
        courses = response.json()["courses"]
        assert len(courses) == 1
        entry = courses[0]
        assert entry["course_slug"] == "tinytorch"
        assert entry["resume_lesson"] == "chapter1--lesson02"
        assert entry["completed_lessons"] == ["chapter1--lesson01"]
        assert entry["xp"] == 25
        assert entry["completed"] is False

    def test_aggregate_questionnaire_to_markdown(self):
        answers = LearnerQuestionnaire(
            goal="Master tensor broadcasting and matrix multiplications",
            preferred_modalities=["spreadsheet", "drawing"],
            understanding_level="beginner",
            tutor_style="solveit",
            pace="unhurried",
            preferred_ui="light",
            custom_notes="Focus on visual matrix dimensions",
        )
        md = aggregate_questionnaire_to_markdown("visual_student", answers)
        fm, body = parse_frontmatter(md)

        assert fm["username"] == "visual_student"
        assert fm["understanding_level"] == "beginner"
        assert fm["preferred_modalities"] == ["spreadsheet", "drawing"]
        assert fm["tutor_style"] == "solveit"
        assert fm["pace"] == "unhurried"
        assert "Master tensor broadcasting" in body
        assert "Focus on visual matrix dimensions" in body
        assert "Offer spreadsheet cell formulas" in body
        assert "Include visual diagrams" in body

    def test_apply_questionnaire_profile_preserves_courses(self, tmp_path: Path):
        # 1. Create initial profile with some progress
        get_or_create_profile("active_student", base_dir=tmp_path)
        record_learner_event(
            username="active_student",
            event_type="lesson_opened",
            payload={"course_slug": "tinytorch", "lesson_slug": "tensor-ops", "ui": "light"},
            base_dir=tmp_path,
        )

        # 2. Re-run questionnaire with new preferences
        answers = LearnerQuestionnaire(
            goal="Build high performance CUDA kernels",
            preferred_modalities=["code"],
            understanding_level="advanced",
            tutor_style="direct",
            pace="sprint",
            preferred_ui="classic",
        )
        content, parsed = apply_questionnaire_profile("active_student", answers, base_dir=tmp_path)

        assert parsed["frontmatter"]["understanding_level"] == "advanced"
        assert parsed["frontmatter"]["tutor_style"] == "direct"
        assert parsed["frontmatter"]["preferred_ui"] == "classic"
        assert any("tinytorch" in line for line in parsed["courses_taken"])
        assert "Build high performance CUDA kernels" in content

    def test_submit_questionnaire_authenticated(self, client, auth_headers, tmp_path: Path):
        payload = {
            "goal": "Understand transformers from zero",
            "preferred_modalities": ["code", "spreadsheet"],
            "understanding_level": "intermediate",
            "tutor_style": "socratic",
            "pace": "unhurried",
            "preferred_ui": "light",
            "custom_notes": "Interested in self-attention weights",
        }
        with patch("learner_profile.get_learners_data_dir", return_value=tmp_path):
            response = client.post(
                "/me/learning-profile/questionnaire",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["parsed"]["frontmatter"]["tutor_style"] == "socratic"
        assert data["parsed"]["frontmatter"]["preferred_modalities"] == ["code", "spreadsheet"]
        assert "Understand transformers from zero" in data["markdown"]

    def test_simplified_diagnostic_inference_modalities_and_tutor(self):
        # Case 1: diagram + guiding question -> drawing+code, socratic
        q1 = LearnerQuestionnaire(
            intake_preference="diagram",
            hint_preference="guiding_question",
            explanation_length="short",
            exercise_format="micro_steps",
            pace="unhurried",
        )
        md1 = aggregate_questionnaire_to_markdown("diag_user", q1)
        fm1, body1 = parse_frontmatter(md1)
        assert fm1["tutor_style"] == "socratic"
        assert fm1["preferred_modalities"] == ["drawing", "code"]
        assert fm1["explanation_length"] == "short"
        assert fm1["exercise_format"] == "micro_steps"
        assert "concise essentials" in body1
        assert "bite-sized micro-steps" in body1

        # Case 2: table + direct explanation -> spreadsheet+code, direct
        q2 = LearnerQuestionnaire(
            intake_preference="table",
            hint_preference="direct_explanation",
            explanation_length="thorough",
            exercise_format="macro_challenges",
            pace="sprint",
        )
        md2 = aggregate_questionnaire_to_markdown("table_user", q2)
        fm2, body2 = parse_frontmatter(md2)
        assert fm2["tutor_style"] == "direct"
        assert fm2["preferred_modalities"] == ["spreadsheet", "code"]
        assert fm2["explanation_length"] == "thorough"
        assert fm2["exercise_format"] == "macro_challenges"
        assert "in-depth explanations" in body2
        assert "comprehensive challenges" in body2

        # Case 3: hands_on + toy example -> code, solveit
        q3 = LearnerQuestionnaire(
            intake_preference="hands_on",
            hint_preference="toy_example",
        )
        md3 = aggregate_questionnaire_to_markdown("code_user", q3)
        fm3, _ = parse_frontmatter(md3)
        assert fm3["tutor_style"] == "solveit"
        assert fm3["preferred_modalities"] == ["code"]

        # Case 4: story -> text+code
        q4 = LearnerQuestionnaire(
            intake_preference="story",
            tone="direct",
        )
        md4 = aggregate_questionnaire_to_markdown("story_user", q4)
        fm4, body4 = parse_frontmatter(md4)
        assert fm4["preferred_modalities"] == ["text", "code"]
        assert fm4["tone"] == "direct"
        assert "Direct technical manual style" in body4
        assert "Anti-AI style" in body4

        # Case 5: guided_completion explicitly selected
        q5 = LearnerQuestionnaire(
            intake_preference="hands_on",
            exercise_format="guided_completion",
        )
        md5 = aggregate_questionnaire_to_markdown("guided_user", q5)
        fm5, body5 = parse_frontmatter(md5)
        assert fm5["exercise_format"] == "guided_completion"
        assert "guided fill-in-the-blank code completion" in body5
        assert "fill-in-the-blank placeholders (`____`)" in body5

        # Case 6: beginner understanding level infers guided_completion if not set
        q6 = LearnerQuestionnaire(
            understanding_level="beginner",
        )
        md6 = aggregate_questionnaire_to_markdown("beginner_user", q6)
        fm6, body6 = parse_frontmatter(md6)
        assert fm6["exercise_format"] == "guided_completion"
        assert "guided fill-in-the-blank code completion" in body6

    def test_submit_questionnaire_with_simplified_diagnostic(
        self, client, auth_headers, tmp_path: Path
    ):
        payload = {
            "intake_preference": "diagram",
            "hint_preference": "guiding_question",
            "explanation_length": "short",
            "exercise_format": "micro_steps",
            "pace": "unhurried",
            "preferred_ui": "light",
            "tone": "pragmatic",
        }
        with patch("learner_profile.get_learners_data_dir", return_value=tmp_path):
            response = client.post(
                "/me/learning-profile/questionnaire",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        fm = data["parsed"]["frontmatter"]
        assert fm["tutor_style"] == "socratic"
        assert fm["preferred_modalities"] == ["drawing", "code"]
        assert fm["explanation_length"] == "short"
        assert fm["exercise_format"] == "micro_steps"
        assert fm["tone"] == "pragmatic"

        # Submit with guided_completion
        payload_guided = {
            "intake_preference": "hands_on",
            "exercise_format": "guided_completion",
            "understanding_level": "beginner",
        }
        with patch("learner_profile.get_learners_data_dir", return_value=tmp_path):
            response_guided = client.post(
                "/me/learning-profile/questionnaire",
                json=payload_guided,
                headers=auth_headers,
            )

        assert response_guided.status_code == 200
        data_guided = response_guided.json()
        fm_guided = data_guided["parsed"]["frontmatter"]
        assert fm_guided["exercise_format"] == "guided_completion"
        assert "guided fill-in-the-blank code completion" in data_guided["parsed"]["snapshot"]
