import os
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from agentic_workflow import CourseGenerationError
from ai_service import ai_service
from auth import User, get_current_user
from course_import import CourseImportError, build_import_instructions, import_course
from llm import providers_public
from routers.file_courses import COURSES_DIR
from run_limits import (
    MAX_AI_CONTEXT_CHARS,
    MAX_AI_HISTORY_MESSAGES,
    MAX_AI_MESSAGE_CHARS,
    enforce_ai_chat_limits,
)
from sandbox_exec import SandboxUnavailableError

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_RESOURCE_CHARS = 8_000


class LearningResource(BaseModel):
    """A learner-supplied reference (notes / docs) used to ground a generated course."""

    kind: str = "text"
    name: str = "learner notes"
    text: str = Field(..., max_length=MAX_RESOURCE_CHARS)


def _find_root_env() -> Path:
    env_override = os.environ.get("ENV_FILE")
    if env_override:
        return Path(env_override)
    cur = Path(__file__).resolve().parent
    for _ in range(6):
        if (cur / ".env").is_file():
            return cur / ".env"
        if (
            (cur / ".git").is_dir() or (cur / "pyproject.toml").is_file()
        ) and cur.name != "backend":
            return cur / ".env"
        cur = cur.parent
    return Path(__file__).resolve().parent.parent.parent / ".env"


def _update_env_file(env_path: Path, key: str, value: str) -> None:
    content = ""
    if env_path.is_file():
        content = env_path.read_text(encoding="utf-8")

    pattern = rf"^\s*{re.escape(key)}=.*"
    replacement = f"{key}={value}"
    if re.search(pattern, content, flags=re.MULTILINE):
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        new_content = content + f"{replacement}\n"

    env_path.write_text(new_content, encoding="utf-8")


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"] = "user"
    content: str = Field(..., min_length=1, max_length=MAX_AI_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Ordered conversation turns (oldest first). The server owns the system
    # prompt and rebuilds it from the learner profile every turn.
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=MAX_AI_HISTORY_MESSAGES)
    # Stable per-session exercise context (lesson + current code). Recomputed by
    # the client each turn, but never includes test_code/solution content.
    context: str | None = Field(default="", max_length=MAX_AI_CONTEXT_CHARS)
    # Optional per-request tutor style override. When absent the learner's
    # LEARNING.md profile is the single source of truth.
    tutor_style: Literal["solveit", "socratic", "direct", "blooms"] | None = None


class ConfigureKeyRequest(BaseModel):
    provider: str = "gemini"
    api_key: str = ""
    model: str | None = None
    api_base: str | None = None
    test_connection: bool = False


class ConfigureKeyResponse(BaseModel):
    success: bool
    message: str
    saved_to_file: bool
    provider: str = ""
    model: str = ""


class TestConnectionRequest(BaseModel):
    provider: str = "ollama"
    api_key: str = ""
    model: str | None = None
    api_base: str | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    provider: str = ""
    model: str = ""


class ProviderInfo(BaseModel):
    id: str
    name: str
    needs_key: bool
    default_model: str
    default_base: str | None = None
    docs_url: str = ""
    blurb: str = ""
    group: str = "key"
    suggested_models: list[str] = Field(default_factory=list)


class AIStatusResponse(BaseModel):
    configured: bool
    has_key: bool
    provider: str
    model: str
    api_base: str | None = None
    providers: list[ProviderInfo] = Field(default_factory=list)


class BuildCourseRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    resources: list[LearningResource] = Field(default_factory=list, max_length=5)


class ToolTraceRead(BaseModel):
    tool_name: str
    status: str = "completed"
    input_summary: str
    output_summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class BuildCourseResponse(BaseModel):
    slug: str
    title: str
    description: str = ""
    narrative_arc: str = ""
    lesson_count: int
    grounded_in: list[str] = Field(default_factory=list)
    tool_traces: list[ToolTraceRead] = Field(default_factory=list)
    solveit_compliance: dict[str, bool] = Field(default_factory=dict)


class CourseInstructionsRequest(BaseModel):
    topic: str = Field(default="", max_length=500)
    resources: list[LearningResource] = Field(default_factory=list, max_length=5)


class CourseInstructionsResponse(BaseModel):
    instructions: str


class LessonVerifyRead(BaseModel):
    order: int
    title: str
    status: str
    solution_passes: bool = False
    starter_fails: bool = False
    detail: str = ""


class ImportCourseResponse(BaseModel):
    slug: str
    title: str
    description: str = ""
    narrative_arc: str = ""
    lesson_count: int
    grounded_in: list[str] = Field(default_factory=list)
    solveit_compliance: dict[str, bool] = Field(default_factory=dict)
    verified: bool = False
    lesson_verifications: list[LessonVerifyRead] = Field(default_factory=list)


class ImportCourseRequest(BaseModel):
    # ``response_markdown`` and ``raw_text`` are aliases: the UI sends
    # ``response_markdown``; API clients may send either. At least one is needed.
    topic: str = Field(default="", max_length=500)
    response_markdown: str | None = None
    raw_text: str | None = None
    verify: bool = True


@router.get("/status", response_model=AIStatusResponse)
def get_ai_status():
    settings = ai_service.settings
    return AIStatusResponse(
        configured=ai_service.is_configured,
        has_key=ai_service.has_key,
        provider=settings.provider,
        model=settings.model,
        api_base=settings.effective_base() if settings.provider else None,
        providers=[ProviderInfo(**p) for p in providers_public()],
    )


@router.post("/configure-key", response_model=ConfigureKeyResponse)
def configure_key(request: Request, body: ConfigureKeyRequest):
    client_host = request.client.host if request.client else ""
    is_local = (
        client_host in ("127.0.0.1", "localhost", "::1", "testclient")
        or os.environ.get("ALLOW_LOCAL_WELCOME", "false").lower() == "true"
    )
    if not is_local:
        raise HTTPException(
            status_code=403,
            detail="Configuring the LLM provider via this endpoint is only permitted in local development.",
        )

    try:
        settings = ai_service.configure(
            provider=body.provider,
            api_key=body.api_key,
            model=body.model,
            api_base=body.api_base,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.test_connection:
        ok, msg = ai_service.check_connection(settings)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)

    env_path = _find_root_env()
    try:
        _update_env_file(env_path, "LLM_PROVIDER", settings.provider)
        _update_env_file(env_path, "LLM_MODEL", settings.model)
        if settings.api_key:
            _update_env_file(env_path, "LLM_API_KEY", settings.api_key)
            if settings.provider == "gemini":
                _update_env_file(env_path, "GEMINI_API_KEY", settings.api_key)
        if settings.api_base:
            _update_env_file(env_path, "LLM_API_BASE", settings.api_base)
    except Exception as e:
        return ConfigureKeyResponse(
            success=True,
            message=f"Provider configured in memory, but could not write to .env: {str(e)}",
            saved_to_file=False,
            provider=settings.provider,
            model=settings.model,
        )

    success_msg = (
        f"{settings.provider} connected successfully and saved to .env"
        if body.test_connection
        else f"{settings.provider} configured and saved to .env"
    )
    return ConfigureKeyResponse(
        success=True,
        message=success_msg,
        saved_to_file=True,
        provider=settings.provider,
        model=settings.model,
    )


@router.post("/test-connection", response_model=TestConnectionResponse)
def test_connection_endpoint(request: Request, body: TestConnectionRequest):
    client_host = request.client.host if request.client else ""
    is_local = (
        client_host in ("127.0.0.1", "localhost", "::1", "testclient")
        or os.environ.get("ALLOW_LOCAL_WELCOME", "false").lower() == "true"
    )
    if not is_local:
        raise HTTPException(
            status_code=403,
            detail="Testing the LLM connection via this endpoint is only permitted in local development.",
        )

    try:
        from llm import validate_settings

        settings = validate_settings(
            provider=body.provider,
            api_key=body.api_key,
            model=body.model,
            api_base=body.api_base,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ok, msg = ai_service.check_connection(settings)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return TestConnectionResponse(
        success=True,
        message=msg,
        provider=settings.provider,
        model=settings.model,
    )


@router.post("/learning-path/build", response_model=BuildCourseResponse)
def build_learning_path(request: BuildCourseRequest, user: User = Depends(get_current_user)):
    """Build a playable, grounded course from a learner's question using agentic tool calls."""
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="A learning topic is required")

    materials = "\n\n".join(r.text for r in request.resources if r.text.strip())

    try:
        result = ai_service.run_agentic_course_builder(
            topic=topic,
            materials=materials,
            username=user.username,
            courses_dir=COURSES_DIR,
        )
    except CourseGenerationError as exc:
        # The builder refused to publish (e.g. no AI model configured, model
        # failed, or lessons needed unowned assets). Nothing was written to disk;
        # surface the honest reason instead of a fake course.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Agentic course creation failed: {exc}"
        ) from exc

    # Record course authorship into LEARNING.md
    try:
        from learner_profile import record_learner_event

        record_learner_event(
            username=user.username,
            event_type="course_authored",
            payload={
                "course_slug": result.slug,
                "title": result.title,
                "lesson_count": result.lesson_count,
            },
        )
    except Exception:
        pass

    return BuildCourseResponse(
        slug=result.slug,
        title=result.title,
        description=result.description,
        narrative_arc=result.narrative_arc,
        lesson_count=result.lesson_count,
        grounded_in=result.grounded_in,
        tool_traces=[
            ToolTraceRead(
                tool_name=t.tool_name,
                status=t.status,
                input_summary=t.input_summary,
                output_summary=t.output_summary,
                details=t.details,
            )
            for t in result.tool_traces
        ],
        solveit_compliance=result.solveit_compliance,
    )


@router.post("/learning-path/instructions", response_model=CourseInstructionsResponse)
def get_course_build_instructions(
    request: CourseInstructionsRequest, user: User = Depends(get_current_user)
):
    """Produce a dead-simple, self-contained copy-paste prompt for a topic.

    Never calls an LLM: the prompt is deterministic and embeds the topic, any
    reference text, the sandbox reality, the Solveit micro-lesson contract, one
    worked example lesson and a strict JSON output format. A learner pastes it
    into any free chat (Gemini/ChatGPT/Claude), then imports the reply.
    """
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="A learning topic is required")

    materials = "\n\n".join(r.text for r in request.resources if r.text.strip())
    return CourseInstructionsResponse(instructions=build_import_instructions(topic, materials))


@router.post("/learning-path/import", response_model=ImportCourseResponse)
def import_learning_path(request: ImportCourseRequest, user: User = Depends(get_current_user)):
    """Import a chat model's pasted reply as a real, verified BaseLayer course.

    No LLM is configured or consulted: the learner produced the reply in their
    own chat. The reply is parsed leniently, validated against the lesson schema,
    every code lesson is verified to actually run (solution+tests pass, starter+
    tests fail), and only then the course is written via the shared writer.
    Nothing is written when the reply cannot produce a runnable course.
    """
    reply = (request.response_markdown or request.raw_text or "").strip()
    if not reply:
        raise HTTPException(
            status_code=422,
            detail="Paste the model's reply (or upload its .md/.json file) to import the course.",
        )

    try:
        result = import_course(
            reply,
            topic=request.topic,
            courses_dir=COURSES_DIR,
            verify=request.verify,
        )
    except CourseImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SandboxUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not verify the course because the code sandbox is unavailable "
                f"({exc}). Lessons are only published after they run, so nothing was written. "
                "Start the app with the Docker sandbox (`./dev.sh`) or Modal credentials, "
                "or pass verify=false to skip the run check."
            ),
        ) from exc

    # Record course authorship into LEARNING.md
    try:
        from learner_profile import record_learner_event

        record_learner_event(
            username=user.username,
            event_type="course_authored",
            payload={
                "course_slug": result.slug,
                "title": result.title,
                "lesson_count": result.lesson_count,
                "source": "chat_import",
            },
        )
    except Exception:
        pass

    return ImportCourseResponse(
        slug=result.slug,
        title=result.title,
        description=result.description,
        narrative_arc=result.narrative_arc,
        lesson_count=result.lesson_count,
        grounded_in=result.grounded_in,
        solveit_compliance=result.solveit_compliance,
        verified=result.verified,
        lesson_verifications=[
            LessonVerifyRead(**record.to_dict()) for record in result.lesson_verifications
        ],
    )


@router.post("/discuss")
def discuss_implementation(request: ChatRequest, user: User = Depends(get_current_user)):
    history = [message.model_dump() for message in request.messages]
    enforce_ai_chat_limits(user.username, history, request.context or "")

    # LEARNING.md is the single source of truth for tutoring style. An explicit
    # per-request override (sent by the same single in-app control, which also
    # persists the choice to the profile) takes precedence for this turn only.
    parsed_profile: dict[str, Any] = {}
    try:
        from learner_profile import get_or_create_profile

        _, parsed_profile = get_or_create_profile(user.username)
    except Exception:
        parsed_profile = {}

    frontmatter = parsed_profile.get("frontmatter", {})
    style = request.tutor_style or frontmatter.get("tutor_style") or "solveit"

    response = ai_service.chat(
        history=history,
        context=request.context or "",
        profile=parsed_profile,
        style=style,
    )
    return {
        "response": response,
        "tutor_style": style,
        "understanding_level": frontmatter.get("understanding_level", "intermediate"),
    }
