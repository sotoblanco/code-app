from contextlib import asynccontextmanager
from typing import List
from sqlmodel import Session, select
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import tempfile
import os

from database import create_db_and_tables, get_session
from models import Course, CourseCreate, CourseRead, Exercise, ExerciseCreate, ExerciseRead, ExerciseUpdate, User
from auth import auth_router, get_current_user, get_current_admin, get_optional_user
from routers.ai import router as ai_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="Coding Exercise App API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(ai_router)

# CORS Setup
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174", # Added fallback port
    "http://127.0.0.1:5174",
]

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

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Coding App Backend Running"}

# --- Admin / Course Routes ---

@app.post("/courses/", response_model=CourseRead)
def create_course(course: CourseCreate, session: Session = Depends(get_session), admin: User = Depends(get_current_admin)):
    db_course = Course.from_orm(course)
    session.add(db_course)
    session.commit()
    session.refresh(db_course)
    return db_course

@app.get("/courses/", response_model=List[CourseRead])
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
def delete_course(course_id: int, session: Session = Depends(get_session), admin: User = Depends(get_current_admin)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    session.delete(course)
    session.commit()
    return None

@app.post("/courses/{course_id}/exercises/", response_model=ExerciseRead)
def create_exercise_for_course(
    course_id: int, exercise: ExerciseCreate, session: Session = Depends(get_session), admin: User = Depends(get_current_admin)
):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    db_exercise = Exercise.from_orm(exercise)
    db_exercise.course_id = course_id
    session.add(db_exercise)
    session.commit()
    session.refresh(db_exercise)
    return db_exercise

    return db_exercise

@app.delete("/courses/{course_id}/exercises/{exercise_id}", status_code=204)
def delete_exercise(
    course_id: int, exercise_id: int, session: Session = Depends(get_session), admin: User = Depends(get_current_admin)
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
    admin: User = Depends(get_current_admin)
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
def run_code(submission: CodeSubmission, user: User = Depends(get_optional_user)):
    # Logic: If running in Modal/Cloud, use Modal Sandbox. Else use Docker.
    execution_env = os.environ.get("EXECUTION_ENV", "docker")

    if execution_env == "modal":
        try:
            # Lazy import to avoid circular dependency
            from modal_app import run_in_sandbox
            
            # Run remotely on Modal
            # Since we are already in a Modal app, this triggers a sandbox creation
            result = run_in_sandbox.remote(submission.code, submission.language)
            return result
        except ImportError:
            raise HTTPException(status_code=500, detail="Modal backend not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    # Default: Use local Docker
    try:
        # Create a temp directory for the execution context
        with tempfile.TemporaryDirectory() as temp_dir:
            # Determine file extension and run command based on language
            filename = "main.py"
            cmd = ["python", "main.py"]
            
            if submission.language == "rust":
                filename = "main.rs"
                # Compile and run
                cmd = ["sh", "-c", "rustc main.rs && ./main"]

            # Write the user code
            code_path = os.path.join(temp_dir, filename)
            with open(code_path, "w") as f:
                f.write(submission.code)
            
            # Construct docker command
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{temp_dir}:/app",
                "-w", "/app",
                "sandbox-runner"
            ] + cmd

            # Run the container
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=5  # 5 second timeout
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
            
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out", "exit_code": 124}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Static Files & SPA Routing ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve static assets (JS, CSS, images)
# Check if /assets exists (it will in Modal, but maybe not locally without mount)
if os.path.exists("/assets"):
    app.mount("/assets", StaticFiles(directory="/assets/assets"), name="assets")
    
    # Catch-all for SPA routing (serving index.html)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow API routes to pass through if they weren't caught above
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
             raise HTTPException(status_code=404, detail="Not Found")
             
        # Serve index.html for any other route (React Router handles the rest)
        return FileResponse("/assets/index.html")
