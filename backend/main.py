import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select

from auth import auth_router, get_current_admin, get_current_user
from database import create_db_and_tables, get_session
from models import (
    Course,
    CourseCreate,
    CourseRead,
    Exercise,
    ExerciseCreate,
    ExerciseRead,
    ExerciseUpdate,
    User,
)
from routers.ai import router as ai_router
from routers.file_courses import router as file_courses_router
from routers.me import router as me_router
from run_limits import enforce_run_limits
from sandbox_exec import SandboxUnavailableError, execute_docker


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="BaseLayer App API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(file_courses_router)
app.include_router(me_router)


# CORS Setup
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
env_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "https://sotoblanco263542--code-app-fastapi-app.modal.run",
] + env_origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeSubmission(BaseModel):
    code: str
    language: str = "python"
    test_code: str | None = None


@app.get("/")
async def read_root():
    if os.path.exists("/assets/index.html"):
        return FileResponse("/assets/index.html")
    return {"status": "ok", "message": "BaseLayer App Backend Running"}


# --- Admin / Course Routes ---


@app.post("/courses/", response_model=CourseRead)
def create_course(
    course: CourseCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    db_course = Course.model_validate(course)
    session.add(db_course)
    session.commit()
    session.refresh(db_course)
    return db_course


@app.get("/courses/", response_model=list[CourseRead])
def read_courses(session: Session = Depends(get_session)):
    courses = session.exec(select(Course)).all()
    return courses


@app.get("/courses/{course_id}", response_model=CourseRead)
def read_course(course_id: int, session: Session = Depends(get_session)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@app.delete("/courses/{course_id}", status_code=204)
def delete_course(
    course_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    session.delete(course)
    session.commit()
    return None


@app.post("/courses/{course_id}/exercises/", response_model=ExerciseRead)
def create_exercise_for_course(
    course_id: int,
    exercise: ExerciseCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    db_exercise = Exercise.model_validate(exercise)
    db_exercise.course_id = course_id
    session.add(db_exercise)
    session.commit()
    session.refresh(db_exercise)
    return db_exercise


@app.delete("/courses/{course_id}/exercises/{exercise_id}", status_code=204)
def delete_exercise(
    course_id: int,
    exercise_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    exercise = session.get(Exercise, exercise_id)
    if not exercise or exercise.course_id != course_id:
        raise HTTPException(status_code=404, detail="Exercise not found")
    session.delete(exercise)
    session.commit()
    return None


@app.put("/courses/{course_id}/exercises/{exercise_id}", response_model=ExerciseRead)
def update_exercise(
    course_id: int,
    exercise_id: int,
    exercise_update: ExerciseUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    db_exercise = session.get(Exercise, exercise_id)
    if not db_exercise or db_exercise.course_id != course_id:
        raise HTTPException(status_code=404, detail="Exercise not found")

    exercise_data = exercise_update.dict(exclude_unset=True)
    for key, value in exercise_data.items():
        setattr(db_exercise, key, value)

    session.add(db_exercise)
    session.commit()
    session.refresh(db_exercise)
    return db_exercise


@app.post("/run")
def run_code(submission: CodeSubmission, user: User = Depends(get_current_user)):
    enforce_run_limits(
        user.username, submission.code, submission.language, submission.test_code or ""
    )
    execution_env = os.environ.get("EXECUTION_ENV", "docker")

    if execution_env == "modal":
        try:
            # Lazy import to avoid circular dependency
            from modal_app import run_in_sandbox

            return run_in_sandbox.remote(
                submission.code, submission.language, submission.test_code or ""
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="Modal backend not found") from None
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    # Default: Use local Docker (shared executor, identical resource caps/cleanup).
    try:
        result = execute_docker(submission.code, submission.language, submission.test_code or "")
    except SandboxUnavailableError as exc:
        # Docker (or another required executable) not found on the host. Return a
        # structured response instead of raising so the frontend can display a
        # helpful message instead of 'undefined'.
        return {"stdout": "", "stderr": str(exc), "exit_code": -1}

    # Record run result into LEARNING.md (only for runs that actually executed).
    if result.get("exit_code") in (-1, 124):
        return result
    try:
        from learner_profile import record_learner_event

        record_learner_event(
            username=user.username,
            event_type="run_result",
            payload={
                "success": result.get("exit_code") == 0,
                "is_submit": bool(submission.test_code and submission.test_code.strip()),
                "language": submission.language,
            },
        )
    except Exception:
        pass

    return result


# Serve static assets (JS, CSS, images)
# Check if /assets exists (it will in Modal, but maybe not locally without mount)
if os.path.exists("/assets"):
    app.mount("/assets", StaticFiles(directory="/assets/assets"), name="assets")

    # Catch-all for SPA routing (serving index.html)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow API routes to pass through if they weren't caught above
        if (
            full_path.startswith("api/")
            or full_path.startswith("docs")
            or full_path.startswith("openapi.json")
        ):
            raise HTTPException(status_code=404, detail="Not Found")

        # Serve index.html for any other route (React Router handles the rest)
        return FileResponse("/assets/index.html")
