"""
Router for file-based courses.

Reads courses from the 'courses/' directory structure:
courses/
└── {course_slug}/
    └── {lesson_slug}/
        ├── main.py      # Initial code template
        ├── test.py      # Test cases
        └── README.md    # Exercise instructions
"""

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ai_service import ai_service
from auth import get_current_user, get_current_user_for_media
from models import User
from spreadsheet_verification import (
    SheetReadError,
    SpreadsheetTargetCell,
    SpreadsheetVerificationResult,
    VerificationUnavailableError,
    extract_sheet_id,
    grade_sheet,
    parse_success_cells,
    read_user_sheet_values,
)

router = APIRouter(prefix="/file-courses", tags=["file-courses"])


def _find_courses_dir() -> Path:
    env_path = os.environ.get("COURSES_DIR")
    if env_path:
        return Path(env_path)
    cur = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = cur / "courses"
        if candidate.is_dir():
            return candidate
        cur = cur.parent
    return Path(__file__).resolve().parent.parent.parent / "courses"


COURSES_DIR = _find_courses_dir()

_SLUG_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_slug(slug: str) -> bool:
    """Validate that a slug segment contains only alphanumeric, dash, and underscore."""
    return bool(slug and _SLUG_REGEX.fullmatch(slug))


def _validate_lesson_slug(lesson_slug: str) -> bool:
    """Validate lesson slug, which may be 'lesson' or 'chapter--lesson'."""
    if not lesson_slug:
        return False
    parts = lesson_slug.split("--")
    if len(parts) > 2:
        return False
    return all(_validate_slug(p) for p in parts)


def _require_valid_slugs(course_slug: str, lesson_slug: str) -> None:
    if not _validate_slug(course_slug) or not _validate_lesson_slug(lesson_slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")


def _is_safe_subpath(target: Path, parent: Path) -> bool:
    """Ensure target path strictly resides within parent directory (prevents path traversal)."""
    try:
        target_resolved = target.resolve()
        parent_resolved = parent.resolve()
        rel = target_resolved.relative_to(parent_resolved)
        return str(rel) != "." and not str(rel).startswith("..")
    except (ValueError, RuntimeError):
        return False


class FileLessonSummary(BaseModel):
    """Summary of a lesson (for listing)"""

    slug: str
    title: str
    order: int


class FileLesson(BaseModel):
    """Full lesson data"""

    slug: str
    title: str
    description: str  # README content
    initial_code: str  # main.py content
    test_code: str  # test.py content
    solution_code: str = ""  # never included in course payloads; fetch via /solution-code
    has_solution: bool = False
    order: int
    language: str = "python"
    chapter: str | None = None  # Chapter slug (e.g., "chapter1")
    exercise_type: str = "code"  # "code", "spreadsheet", "drawing"
    google_sheet_id: str | None = None  # Google Sheet ID for spreadsheet exercises
    copy_on_open: bool = False  # If true, create a per-user copy when opening
    image_url: str | None = None  # URL for question image (drawing exercises)
    stroke_color: str = "#e11d48"  # Default stroke color for drawing exercises
    stroke_width: int = 4  # Default stroke width for drawing exercises
    skills: list[str] = Field(default_factory=list)
    success_cells: list[SpreadsheetTargetCell] = Field(
        default_factory=list, description="Target cells/expected values for spreadsheet checks"
    )
    hints: list[str] = Field(default_factory=list, description="Lesson-specific hints")


class FileCourseSummary(BaseModel):
    """Summary of a course (for listing)"""

    slug: str
    title: str
    description: str
    lesson_count: int
    skills: list[str] = Field(default_factory=list)


class FileCourse(BaseModel):
    """Full course data with lessons"""

    slug: str
    title: str
    description: str
    lessons: list[FileLesson]
    skills: list[str] = Field(default_factory=list)


class ExportLessonBundle(BaseModel):
    title: str
    slug: str
    order: int = 1
    chapter: str | None = None
    exercise_type: str = "code"
    language: str = "python"
    description: str = ""
    initial_code: str = ""
    test_code: str = ""
    solution_code: str = ""
    skills: list[str] = Field(default_factory=list)
    google_sheet_id: str | None = None
    copy_on_open: bool = False
    stroke_color: str = "#e11d48"
    stroke_width: int = 4
    hints: list[str] = Field(default_factory=list)
    question_image_base64: str | None = None
    solution_image_base64: str | None = None


class ExportCourseBundle(BaseModel):
    version: int = 1
    kind: Literal["course", "lesson"] = "course"
    slug: str
    title: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    lessons: list[ExportLessonBundle] = Field(default_factory=list)


class SingleLessonShareBundle(BaseModel):
    version: int = 1
    kind: Literal["lesson"] = "lesson"
    course_slug: str = "shared-lessons"
    lesson: ExportLessonBundle


class ImportBundleRequest(BaseModel):
    version: int = 1
    kind: Literal["course", "lesson"] = "course"
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)
    lessons: list[ExportLessonBundle] = Field(default_factory=list)
    lesson: ExportLessonBundle | None = None
    target_course_slug: str | None = None


class ImportBundleResponse(BaseModel):
    status: str = "success"
    kind: Literal["course", "lesson"]
    course_slug: str
    lesson_slug: str
    title: str
    lesson_count: int
    message: str


def get_course_title(slug: str) -> str:
    """Convert slug to human-readable title"""
    return slug.replace("-", " ").replace("_", " ").title()


def get_lesson_title(slug: str, order: int) -> str:
    """Convert lesson slug to human-readable title"""
    title = slug.replace("-", " ").replace("_", " ").title()
    return f"Lesson {order}: {title}"


def read_file_content(path: Path) -> str:
    """Read file content, return empty string if not exists"""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def is_lesson_directory(dir_path: Path) -> bool:
    """Check if a directory is a lesson (contains README.md, main.py/main.rs, etc)"""
    readme_exists = (dir_path / "README.md").exists()
    has_main = (dir_path / "main.py").exists() or (dir_path / "main.rs").exists()
    has_metadata = (dir_path / "metadata.json").exists()
    return readme_exists and (has_main or has_metadata)


def _read_json_object(path: Path) -> dict:
    """Load a JSON object from disk, or {} if missing/invalid."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _push_skill(skills: list[str], skill: str | None) -> bool:
    """Append a unique skill. Returns True once the list hits the cap."""
    if skill and skill not in skills:
        skills.append(skill)
    return len(skills) >= 12


def _normalize_skills(raw: object) -> list[str]:
    """Keep unique, non-empty skill tags (max 12)."""
    if not isinstance(raw, list):
        return []
    skills: list[str] = []
    for item in raw:
        if _push_skill(skills, _optional_str(item)):
            break
    return skills


def _heading_from_readme(readme: str) -> str | None:
    for line in readme.splitlines():
        if line.startswith("# "):
            return _optional_str(line[2:])
    return None


def _lesson_display_title(meta_title: str | None, readme: str, slug: str, order: int) -> str:
    if meta_title:
        return meta_title
    heading = _heading_from_readme(readme)
    if heading:
        return heading
    return get_lesson_title(slug, order)


def _unique_lesson_skills(lessons: list[FileLesson]) -> list[str]:
    skills: list[str] = []
    for lesson in lessons:
        for skill in lesson.skills:
            if _push_skill(skills, skill):
                return skills
    return skills


@dataclass
class LessonMeta:
    exercise_type: str = "code"
    google_sheet_id: str | None = None
    copy_on_open: bool = False
    stroke_color: str = "#e11d48"
    stroke_width: int = 4
    image_url: str | None = None
    skills: list[str] = field(default_factory=list)
    title: str | None = None
    success_cells: list[SpreadsheetTargetCell] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)


def _extract_metadata(lesson_path: Path) -> LessonMeta:
    """Extract metadata configuration for lesson."""
    metadata = _read_json_object(lesson_path / "metadata.json")
    exercise_type = metadata.get("exercise_type", "code")
    image_url = None
    if exercise_type == "drawing" and (lesson_path / "question.png").exists():
        image_url = "__image__"
    return LessonMeta(
        exercise_type=exercise_type,
        google_sheet_id=metadata.get("google_sheet_id"),
        copy_on_open=bool(metadata.get("copy_on_open", False)),
        stroke_color=metadata.get("stroke_color", "#e11d48"),
        stroke_width=int(metadata.get("stroke_width", 4)),
        image_url=image_url,
        skills=_normalize_skills(metadata.get("skills")),
        title=_optional_str(metadata.get("title")),
        success_cells=parse_success_cells(metadata.get("success_cells")),
        hints=_normalize_skills(metadata.get("hints"))[:5],
    )


def _detect_language_and_files(lesson_path: Path) -> tuple[str, Path, Path, Path]:
    """Detect language and return paths to main, test, and solution files."""
    if (lesson_path / "main.rs").exists():
        return "rust", lesson_path / "main.rs", lesson_path / "test.rs", lesson_path / "solution.rs"
    return "python", lesson_path / "main.py", lesson_path / "test.py", lesson_path / "solution.py"


def parse_lesson(
    course_path: Path, lesson_dir_name: str, order: int, chapter_slug: str | None = None
) -> FileLesson | None:
    """Parse a lesson directory into a FileLesson object"""
    lesson_path = course_path / lesson_dir_name
    readme_path = lesson_path / "README.md"

    if not lesson_path.is_dir() or not readme_path.exists():
        return None

    meta = _extract_metadata(lesson_path)
    language, main_path, test_path, solution_path = _detect_language_and_files(lesson_path)
    final_slug = f"{chapter_slug}--{lesson_dir_name}" if chapter_slug else lesson_dir_name
    description = read_file_content(readme_path)

    return FileLesson(
        slug=final_slug,
        title=_lesson_display_title(meta.title, description, lesson_dir_name, order),
        description=description,
        initial_code=read_file_content(main_path),
        test_code=read_file_content(test_path),
        solution_code="",
        has_solution=solution_path.exists(),
        order=order,
        language=language,
        chapter=chapter_slug,
        exercise_type=meta.exercise_type,
        google_sheet_id=meta.google_sheet_id,
        copy_on_open=meta.copy_on_open,
        image_url=meta.image_url,
        stroke_color=meta.stroke_color,
        stroke_width=meta.stroke_width,
        skills=meta.skills,
        success_cells=meta.success_cells,
        hints=meta.hints,
    )


def _is_chapter_dir(d: Path) -> bool:
    """Return True if directory contains at least one lesson subdirectory."""
    if not d.is_dir() or d.name.startswith("."):
        return False
    return any(is_lesson_directory(sub) for sub in d.iterdir() if sub.is_dir())


def _has_chapters(subdirs: list[Path]) -> bool:
    """Check if course directory contains chapter subdirectories."""
    return any(_is_chapter_dir(d) for d in subdirs)


def _get_valid_subdirs(dir_path: Path) -> list[Path]:
    """Return sorted list of non-hidden subdirectories."""
    return sorted([d for d in dir_path.iterdir() if d.is_dir() and not d.name.startswith(".")])


def _parse_lessons_in_chapter(chapter_dir: Path, start_order: int) -> list[FileLesson]:
    """Parse all lessons in a single chapter directory."""
    lessons: list[FileLesson] = []
    order = start_order
    for lesson_dir in _get_valid_subdirs(chapter_dir):
        lesson = parse_lesson(chapter_dir, lesson_dir.name, order, chapter_slug=chapter_dir.name)
        if lesson:
            lessons.append(lesson)
            order += 1
    return lessons


def _collect_chapter_lessons(subdirs: list[Path]) -> list[FileLesson]:
    """Collect all lessons structured within chapter subdirectories."""
    lessons: list[FileLesson] = []
    for chapter_dir in subdirs:
        if chapter_dir.is_dir() and not chapter_dir.name.startswith("."):
            chapter_lessons = _parse_lessons_in_chapter(chapter_dir, len(lessons) + 1)
            lessons.extend(chapter_lessons)
    return lessons


def _collect_flat_lessons(course_path: Path, subdirs: list[Path]) -> list[FileLesson]:
    """Collect lessons located directly under the course directory."""
    lessons: list[FileLesson] = []
    order = 1
    for lesson_dir in subdirs:
        lesson = parse_lesson(course_path, lesson_dir.name, order)
        if lesson:
            lessons.append(lesson)
            order += 1
    return lessons


def _collect_course_lessons(course_path: Path, subdirs: list[Path]) -> list[FileLesson]:
    """Collect lessons based on chapter or flat directory structure."""
    if _has_chapters(subdirs):
        return _collect_chapter_lessons(subdirs)
    return _collect_flat_lessons(course_path, subdirs)


def _get_course_description(course_path: Path, course_slug: str) -> str:
    """Extract first line of course README or fallback description."""
    course_readme = course_path / "README.md"
    if course_readme.exists():
        desc = read_file_content(course_readme)
        if desc:
            return desc.split("\n")[0]
    return f"Learn {get_course_title(course_slug)}"


def _course_title(meta: dict, course_slug: str) -> str:
    return _optional_str(meta.get("title")) or get_course_title(course_slug)


def _course_blurb(meta: dict, course_path: Path, course_slug: str) -> str:
    return _optional_str(meta.get("description")) or _get_course_description(
        course_path, course_slug
    )


def _course_skills(meta: dict, lessons: list[FileLesson]) -> list[str]:
    return _normalize_skills(meta.get("skills")) or _unique_lesson_skills(lessons)


def parse_course(course_slug: str) -> FileCourse | None:
    """Parse a course directory into a FileCourse object"""
    course_path = _get_safe_course_dir(course_slug)
    if not course_path:
        return None
    lessons = _collect_course_lessons(course_path, _get_valid_subdirs(course_path))
    meta = _read_json_object(course_path / "metadata.json")
    return FileCourse(
        slug=course_slug,
        title=_course_title(meta, course_slug),
        description=_course_blurb(meta, course_path, course_slug),
        lessons=lessons,
        skills=_course_skills(meta, lessons),
    )


def _course_summary_from_dir(course_dir: Path) -> FileCourseSummary | None:
    """Build FileCourseSummary from a course directory if valid."""
    if not course_dir.is_dir() or course_dir.name.startswith("."):
        return None
    course = parse_course(course_dir.name)
    if not course or not course.lessons:
        return None
    return FileCourseSummary(
        slug=course.slug,
        title=course.title,
        description=course.description,
        lesson_count=len(course.lessons),
        skills=course.skills,
    )


@router.get("/", response_model=list[FileCourseSummary])
def list_file_courses():
    """List all available file-based courses"""
    if not COURSES_DIR.exists():
        return []

    summaries = [_course_summary_from_dir(d) for d in sorted(COURSES_DIR.iterdir())]
    return [s for s in summaries if s is not None]


def _get_course_or_404(course_slug: str) -> FileCourse:
    if not _validate_slug(course_slug):
        raise HTTPException(status_code=400, detail="Invalid course slug format")
    course = parse_course(course_slug)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{course_slug}' not found")
    return course


def _find_lesson_in_course_or_404(course: FileCourse, lesson_slug: str) -> FileLesson:
    for lesson in course.lessons:
        if lesson.slug == lesson_slug:
            return lesson
    raise HTTPException(
        status_code=404, detail=f"Lesson '{lesson_slug}' not found in course '{course.slug}'"
    )


def _get_safe_course_dir(course_slug: str) -> Path | None:
    if not _validate_slug(course_slug):
        return None
    course_path = COURSES_DIR / course_slug
    if not _is_safe_subpath(course_path, COURSES_DIR) or not course_path.is_dir():
        return None
    return course_path


def _resolve_direct_lesson_path(course_path: Path, lesson_slug: str) -> Path:
    if "--" in lesson_slug:
        chapter_dir, lesson_dir = lesson_slug.split("--", 1)
        return course_path / chapter_dir / lesson_dir
    return course_path / lesson_slug


def _search_course_rglob(course_path: Path, lesson_slug: str) -> Path | None:
    for entry in course_path.rglob(f"{lesson_slug}"):
        if entry.is_dir() and _is_safe_subpath(entry, course_path):
            return entry
    return None


def _find_lesson_in_course_dir(course_path: Path, lesson_slug: str) -> Path | None:
    direct = _resolve_direct_lesson_path(course_path, lesson_slug)
    if direct.is_dir() and _is_safe_subpath(direct, course_path):
        return direct
    return _search_course_rglob(course_path, lesson_slug)


def get_lesson_path(course_slug: str, lesson_slug: str) -> Path | None:
    """Resolve the slug to its physical directory path safely."""
    if not _validate_lesson_slug(lesson_slug):
        return None
    course_path = _get_safe_course_dir(course_slug)
    if not course_path:
        return None
    return _find_lesson_in_course_dir(course_path, lesson_slug)


def _encode_image_file_base64(path: Path) -> str | None:
    if path.is_file():
        try:
            return base64.b64encode(path.read_bytes()).decode("ascii")
        except OSError:
            return None
    return None


def _decode_image_base64_safely(data: str | None) -> bytes | None:
    if not data:
        return None
    try:
        raw = data.split(",", 1)[1] if "," in data else data
        return base64.b64decode(raw)
    except Exception:
        return None


def _extract_lesson_solution(lesson_dir: Path | None) -> str:
    if not lesson_dir or not lesson_dir.is_dir():
        return ""
    _lang, _m, _t, sol_path = _detect_language_and_files(lesson_dir)
    return read_file_content(sol_path) if sol_path.is_file() else ""


def _extract_lesson_images(lesson_dir: Path | None) -> tuple[str | None, str | None]:
    if not lesson_dir or not lesson_dir.is_dir():
        return None, None
    q_img = _encode_image_file_base64(lesson_dir / "question.png")
    s_img = _encode_image_file_base64(lesson_dir / "solution.png")
    return q_img, s_img


def _lesson_to_export_bundle(course_path: Path, lesson: FileLesson) -> ExportLessonBundle:
    lesson_dir = _find_lesson_in_course_dir(course_path, lesson.slug)
    solution_code = _extract_lesson_solution(lesson_dir)
    q_img, s_img = _extract_lesson_images(lesson_dir)
    return ExportLessonBundle(
        title=lesson.title,
        slug=lesson.slug,
        order=lesson.order,
        chapter=lesson.chapter,
        exercise_type=lesson.exercise_type,
        language=lesson.language,
        description=lesson.description,
        initial_code=lesson.initial_code,
        test_code=lesson.test_code,
        solution_code=solution_code,
        skills=lesson.skills,
        google_sheet_id=lesson.google_sheet_id,
        copy_on_open=lesson.copy_on_open,
        stroke_color=lesson.stroke_color,
        stroke_width=lesson.stroke_width,
        hints=lesson.hints,
        question_image_base64=q_img,
        solution_image_base64=s_img,
    )


def _sanitize_slug(raw: str, default: str = "imported") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw.strip()).strip("-").lower()
    return cleaned[:50] or default


def _pick_safe_import_course_dir(base_slug: str) -> tuple[str, Path]:
    slug = _sanitize_slug(base_slug, "imported-course")
    target = COURSES_DIR / slug
    if not target.exists():
        return slug, target
    target_imported = COURSES_DIR / f"{slug}-imported"
    if not target_imported.exists():
        return f"{slug}-imported", target_imported
    suffix = int(time.time()) % 10000
    unique_slug = f"{slug}-{suffix}"
    return unique_slug, COURSES_DIR / unique_slug


_CODE_FILE_EXTENSIONS: dict[str, tuple[str, str, str]] = {
    "rust": ("main.rs", "test.rs", "solution.rs"),
    "python": ("main.py", "test.py", "solution.py"),
}


def _write_code_files(lesson_dir: Path, lesson: ExportLessonBundle) -> None:
    names = _CODE_FILE_EXTENSIONS.get(lesson.language, _CODE_FILE_EXTENSIONS["python"])
    code_text = lesson.initial_code if lesson.initial_code else "# Start here\n"
    test_text = lesson.test_code if lesson.test_code else "assert True\n"
    (lesson_dir / names[0]).write_text(code_text, encoding="utf-8")
    (lesson_dir / names[1]).write_text(test_text, encoding="utf-8")
    if lesson.solution_code:
        (lesson_dir / names[2]).write_text(lesson.solution_code, encoding="utf-8")


def _write_drawing_files(lesson_dir: Path, lesson: ExportLessonBundle) -> None:
    q_bytes = _decode_image_base64_safely(lesson.question_image_base64)
    if q_bytes:
        (lesson_dir / "question.png").write_bytes(q_bytes)
    s_bytes = _decode_image_base64_safely(lesson.solution_image_base64)
    if s_bytes:
        (lesson_dir / "solution.png").write_bytes(s_bytes)


def _write_exercise_specific_files(lesson_dir: Path, lesson: ExportLessonBundle) -> None:
    if lesson.exercise_type == "code":
        _write_code_files(lesson_dir, lesson)
    elif lesson.exercise_type == "drawing":
        _write_drawing_files(lesson_dir, lesson)


def _write_lesson_bundle_files(lesson_dir: Path, lesson: ExportLessonBundle) -> None:
    lesson_dir.mkdir(parents=True, exist_ok=True)
    readme_content = lesson.description or f"# {lesson.title}\n"
    (lesson_dir / "README.md").write_text(readme_content, encoding="utf-8")
    meta: dict[str, Any] = {
        "exercise_type": lesson.exercise_type,
        "skills": lesson.skills,
        "title": lesson.title,
        "google_sheet_id": lesson.google_sheet_id,
        "copy_on_open": lesson.copy_on_open,
        "stroke_color": lesson.stroke_color,
        "stroke_width": lesson.stroke_width,
        "hints": lesson.hints,
    }
    (lesson_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _write_exercise_specific_files(lesson_dir, lesson)


def _materialize_course_lessons(target_dir: Path, lessons: list[ExportLessonBundle]) -> str:
    first_slug = ""
    for idx, les in enumerate(lessons, start=1):
        clean_ch = _sanitize_slug(les.chapter or "chapter1", "chapter1")
        clean_l_slug = _sanitize_slug(les.slug or f"lesson{idx:02d}", f"lesson{idx:02d}")
        _write_lesson_bundle_files(target_dir / clean_ch / clean_l_slug, les)
        if not first_slug:
            first_slug = f"{clean_ch}--{clean_l_slug}"
    return first_slug


def _course_base_name(bundle: ImportBundleRequest) -> str:
    if bundle.slug:
        return bundle.slug
    if bundle.title:
        return bundle.title
    return "imported-course"


def _write_course_root_metadata(target_dir: Path, title: str, desc: str, skills: list[str]) -> None:
    (target_dir / "README.md").write_text(f"# {title}\n\n{desc}\n", encoding="utf-8")
    meta = {"title": title, "skills": skills, "description": desc}
    (target_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _import_course_bundle(bundle: ImportBundleRequest) -> ImportBundleResponse:
    if not bundle.lessons:
        raise HTTPException(
            status_code=400, detail="Course bundle must contain at least one lesson."
        )

    base = _course_base_name(bundle)
    course_slug, target_dir = _pick_safe_import_course_dir(base)
    target_dir.mkdir(parents=True, exist_ok=True)

    title = bundle.title or get_course_title(course_slug)
    desc = bundle.description or f"Learn {title}"
    _write_course_root_metadata(target_dir, title, desc, bundle.skills)

    first_slug = _materialize_course_lessons(target_dir, bundle.lessons)
    return ImportBundleResponse(
        status="success",
        kind="course",
        course_slug=course_slug,
        lesson_slug=first_slug,
        title=title,
        lesson_count=len(bundle.lessons),
        message=f"Course '{title}' imported successfully.",
    )


def _import_lesson_into_existing_course(
    target_course_slug: str, lesson: ExportLessonBundle
) -> ImportBundleResponse:
    course_dir = _get_safe_course_dir(target_course_slug)
    if not course_dir:
        raise HTTPException(
            status_code=404, detail=f"Target course '{target_course_slug}' not found."
        )
    clean_ch = _sanitize_slug(lesson.chapter or "chapter1", "chapter1")
    clean_l = _sanitize_slug(lesson.slug or "lesson-imported", "lesson-imported")
    _write_lesson_bundle_files(course_dir / clean_ch / clean_l, lesson)
    return ImportBundleResponse(
        status="success",
        kind="lesson",
        course_slug=target_course_slug,
        lesson_slug=f"{clean_ch}--{clean_l}",
        title=lesson.title,
        lesson_count=1,
        message=f"Lesson '{lesson.title}' imported into '{target_course_slug}'.",
    )


def _extract_lesson_summary_desc(lesson: ExportLessonBundle, title: str) -> str:
    if lesson.description:
        return lesson.description.splitlines()[0].lstrip("#").strip()
    return f"Learn {title}"


def _import_lesson_as_new_course(lesson: ExportLessonBundle) -> ImportBundleResponse:
    clean_base = f"shared-{_sanitize_slug(lesson.slug or lesson.title or 'lesson', 'lesson')}"
    course_slug, course_dir = _pick_safe_import_course_dir(clean_base)
    course_dir.mkdir(parents=True, exist_ok=True)
    title = lesson.title or get_course_title(course_slug)
    desc = _extract_lesson_summary_desc(lesson, title)
    _write_course_root_metadata(course_dir, title, desc, lesson.skills)

    clean_l = _sanitize_slug(lesson.slug or "lesson01", "lesson01")
    _write_lesson_bundle_files(course_dir / "chapter1" / clean_l, lesson)
    return ImportBundleResponse(
        status="success",
        kind="lesson",
        course_slug=course_slug,
        lesson_slug=f"chapter1--{clean_l}",
        title=title,
        lesson_count=1,
        message=f"Lesson '{title}' imported successfully.",
    )


def _import_single_lesson_bundle(bundle: ImportBundleRequest) -> ImportBundleResponse:
    lesson = bundle.lesson or (bundle.lessons[0] if bundle.lessons else None)
    if not lesson:
        raise HTTPException(status_code=400, detail="Lesson bundle must contain lesson data.")

    if bundle.target_course_slug:
        return _import_lesson_into_existing_course(bundle.target_course_slug, lesson)
    return _import_lesson_as_new_course(lesson)


@router.post("/import", response_model=ImportBundleResponse)
def import_course_or_lesson_bundle(
    bundle: ImportBundleRequest, user: User = Depends(get_current_user)
):
    """Import a shared course or single lesson into the platform."""
    if bundle.kind == "lesson" or (bundle.lesson is not None and not bundle.lessons):
        return _import_single_lesson_bundle(bundle)
    return _import_course_bundle(bundle)


@router.get("/{course_slug}/export", response_model=ExportCourseBundle)
def export_course_bundle(course_slug: str, user: User = Depends(get_current_user)):
    """Export an entire course with all lessons into a portable JSON bundle."""
    course = _get_course_or_404(course_slug)
    course_path = _get_safe_course_dir(course_slug)
    if not course_path:
        raise HTTPException(status_code=404, detail="Course directory not found")

    bundles = [_lesson_to_export_bundle(course_path, item) for item in course.lessons]
    return ExportCourseBundle(
        version=1,
        kind="course",
        slug=course.slug,
        title=course.title,
        description=course.description,
        skills=course.skills,
        lessons=bundles,
    )


@router.get("/{course_slug}/{lesson_slug}/export", response_model=SingleLessonShareBundle)
def export_single_lesson_bundle(
    course_slug: str, lesson_slug: str, user: User = Depends(get_current_user)
):
    """Export a single lesson into a portable JSON bundle for sharing."""
    _require_valid_slugs(course_slug, lesson_slug)
    course = _get_course_or_404(course_slug)
    lesson = _find_lesson_in_course_or_404(course, lesson_slug)
    course_path = _get_safe_course_dir(course_slug)
    if not course_path:
        raise HTTPException(status_code=404, detail="Course directory not found")

    bundle = _lesson_to_export_bundle(course_path, lesson)
    return SingleLessonShareBundle(
        version=1,
        kind="lesson",
        course_slug=course_slug,
        lesson=bundle,
    )


@router.get("/{course_slug}", response_model=FileCourse)
def get_file_course(course_slug: str, user: User = Depends(get_current_user)):
    """Get a specific file-based course with all its lessons"""
    return _get_course_or_404(course_slug)


@router.get("/{course_slug}/{lesson_slug}", response_model=FileLesson)
def get_file_lesson(course_slug: str, lesson_slug: str, user: User = Depends(get_current_user)):
    """Get a specific lesson from a file-based course"""
    _require_valid_slugs(course_slug, lesson_slug)
    course = _get_course_or_404(course_slug)
    return _find_lesson_in_course_or_404(course, lesson_slug)


def _get_safe_lesson_dir_or_404(course_slug: str, lesson_slug: str) -> Path:
    _require_valid_slugs(course_slug, lesson_slug)
    lesson_dir = get_lesson_path(course_slug, lesson_slug)
    if not lesson_dir:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson_dir


def _get_safe_media_file_or_404(lesson_dir: Path, filename: str) -> Path:
    image_path = lesson_dir / filename
    if not _is_safe_subpath(image_path, COURSES_DIR) or not image_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found for this lesson")
    return image_path


@router.get("/{course_slug}/{lesson_slug}/image")
def get_lesson_image(
    course_slug: str,
    lesson_slug: str,
    user: User = Depends(get_current_user_for_media),
):
    """Serve the question.png image for a drawing exercise."""
    lesson_dir = _get_safe_lesson_dir_or_404(course_slug, lesson_slug)
    image_path = _get_safe_media_file_or_404(lesson_dir, "question.png")
    return FileResponse(
        str(image_path),
        media_type="image/png",
        headers={"Cache-Control": "private, no-cache"},
    )


class SolutionCodeRead(BaseModel):
    solution_code: str


def _read_safe_solution_code(lesson_dir: Path) -> str:
    _language, _main, _test, solution_path = _detect_language_and_files(lesson_dir)
    if not _is_safe_subpath(solution_path, COURSES_DIR):
        raise HTTPException(status_code=403, detail="Access denied")
    content = read_file_content(solution_path)
    if not content:
        raise HTTPException(status_code=404, detail="Solution not found")
    return content


@router.get("/{course_slug}/{lesson_slug}/solution-code", response_model=SolutionCodeRead)
def get_lesson_solution_code(
    course_slug: str, lesson_slug: str, user: User = Depends(get_current_user)
):
    lesson_dir = _get_safe_lesson_dir_or_404(course_slug, lesson_slug)
    return SolutionCodeRead(solution_code=_read_safe_solution_code(lesson_dir))


@router.get("/{course_slug}/{lesson_slug}/solution")
def get_lesson_solution(
    course_slug: str,
    lesson_slug: str,
    user: User = Depends(get_current_user_for_media),
):
    """Serve the solution.png image for a drawing exercise."""
    lesson_dir = _get_safe_lesson_dir_or_404(course_slug, lesson_slug)
    image_path = _get_safe_media_file_or_404(lesson_dir, "solution.png")
    return FileResponse(
        str(image_path),
        media_type="image/png",
        headers={"Cache-Control": "private, no-store"},
    )


class DrawingSubmission(BaseModel):
    image_data: str  # base64-encoded PNG from the canvas
    xp: int | None = Field(default=None, ge=0, le=500)  # XP earned by the learner's player UI


def _decode_sketch_image(raw_image_data: str) -> bytes:
    """Decode base64 canvas image data."""
    data = raw_image_data
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        return base64.b64decode(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}") from e


def _load_drawing_context_files(lesson_dir: Path) -> tuple[str, bytes, bytes | None]:
    """Load instructions, question image, and optional solution image."""
    readme_path = lesson_dir / "README.md"
    instructions = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

    question_path = lesson_dir / "question.png"
    if not question_path.exists():
        raise HTTPException(status_code=500, detail="Lesson diagram missing (question.png)")
    question_img_bytes = question_path.read_bytes()

    solution_path = lesson_dir / "solution.png"
    solution_img_bytes = solution_path.read_bytes() if solution_path.exists() else None

    return instructions, question_img_bytes, solution_img_bytes


@router.post("/{course_slug}/{lesson_slug}/submit-drawing")
def submit_drawing(
    course_slug: str,
    lesson_slug: str,
    submission: DrawingSubmission,
    user: User = Depends(get_current_user),
):
    """Evaluate a drawing submission using AI, returning structured rubric feedback."""
    lesson_dir = _get_safe_lesson_dir_or_404(course_slug, lesson_slug)
    instructions, question_bytes, solution_bytes = _load_drawing_context_files(lesson_dir)
    sketch_bytes = _decode_sketch_image(submission.image_data)

    result = ai_service.evaluate_drawing(instructions, question_bytes, sketch_bytes, solution_bytes)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    if result.get("passed"):
        _record_modality_pass(user.username, course_slug, lesson_slug, "drawing", xp=submission.xp)
    return result


def _validate_spreadsheet_lesson(lesson: FileLesson) -> FileLesson:
    """Validate that a lesson is a spreadsheet exercise with template id."""
    if lesson.exercise_type != "spreadsheet" or not lesson.google_sheet_id:
        raise HTTPException(
            status_code=400,
            detail="Lesson is not a spreadsheet exercise or has no template sheet id",
        )
    return lesson


def _find_lesson_for_copy(course_slug: str, lesson_slug: str) -> FileLesson:
    """Find and validate lesson for spreadsheet copy."""
    _require_valid_slugs(course_slug, lesson_slug)
    course = _get_course_or_404(course_slug)
    lesson = _find_lesson_in_course_or_404(course, lesson_slug)
    return _validate_spreadsheet_lesson(lesson)


def _get_service_account_path() -> str:
    """Retrieve service account file path from environment."""
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE") or os.environ.get(
        "SERVICE_ACCOUNT_FILE"
    )
    if not sa_file:
        raise HTTPException(
            status_code=501,
            detail="Service account file not configured. Set GOOGLE_SERVICE_ACCOUNT_FILE env var.",
        )
    return sa_file


@router.post("/{course_slug}/{lesson_slug}/copy-sheet")
def create_sheet_copy(course_slug: str, lesson_slug: str, user: User = Depends(get_current_user)):
    """Create a per-user copy of a template Google Sheet for a lesson."""
    lesson = _find_lesson_for_copy(course_slug, lesson_slug)
    sa_file = _get_service_account_path()

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except Exception:
        raise HTTPException(
            status_code=501, detail="googleapiclient not installed on server"
        ) from None

    try:
        creds = Credentials.from_service_account_file(
            sa_file, scopes=["https://www.googleapis.com/auth/drive"]
        )
        drive = build("drive", "v3", credentials=creds)
        new_title = f"{course_slug}-{lesson_slug}-copy-{int(time.time())}"
        copied = (
            drive.files().copy(fileId=lesson.google_sheet_id, body={"name": new_title}).execute()
        )
        new_id = copied.get("id")
        return {
            "google_sheet_id": new_id,
            "url": f"https://docs.google.com/spreadsheets/d/{new_id}/edit",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create sheet copy: {e}") from e


class SpreadsheetVerificationRequest(BaseModel):
    sheet_id: str  # Student copy URL or bare sheet id
    xp: int | None = Field(default=None, ge=0, le=500)  # XP earned by the learner's player UI


def _record_modality_pass(
    username: str,
    course_slug: str,
    lesson_slug: str,
    modality: str,
    xp: int | None = None,
) -> None:
    """Record a passing submission into the learner's LEARNING.md (best-effort)."""
    payload: dict[str, Any] = {
        "course_slug": course_slug,
        "lesson_slug": lesson_slug,
        "modality": modality,
    }
    if xp is not None:
        payload["xp"] = xp
    try:
        from learner_profile import record_learner_event

        record_learner_event(
            username=username,
            event_type="lesson_passed",
            payload=payload,
        )
    except Exception:
        pass


def _validate_verifiable_spreadsheet(course_slug: str, lesson_slug: str) -> FileLesson:
    """Find a spreadsheet lesson that defines success_cells to verify against."""
    lesson = _find_lesson_for_copy(course_slug, lesson_slug)
    if not lesson.success_cells:
        raise HTTPException(
            status_code=400,
            detail="This spreadsheet lesson does not define success_cells to verify against.",
        )
    return lesson


@router.post(
    "/{course_slug}/{lesson_slug}/verify-sheet",
    response_model=SpreadsheetVerificationResult,
)
def verify_spreadsheet(
    course_slug: str,
    lesson_slug: str,
    submission: SpreadsheetVerificationRequest,
    user: User = Depends(get_current_user),
):
    """Verify a student's sheet copy against the lesson's target cells (Issue #75)."""
    lesson = _validate_verifiable_spreadsheet(course_slug, lesson_slug)
    sheet_id = extract_sheet_id(submission.sheet_id)
    if not sheet_id:
        raise HTTPException(
            status_code=400, detail="Provide a Google Sheets URL or a valid sheet id."
        )

    try:
        actual_values = read_user_sheet_values(sheet_id)
    except VerificationUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except SheetReadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result = grade_sheet(lesson.success_cells, actual_values)
    if result.passed:
        _record_modality_pass(
            user.username, course_slug, lesson_slug, "spreadsheet", xp=submission.xp
        )
    return result
