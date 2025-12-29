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
from models import Course, CourseCreate, CourseRead, Exercise, ExerciseCreate, ExerciseRead, User
from auth import auth_router, get_current_user, get_current_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="Coding Exercise App API", lifespan=lifespan)
app.include_router(auth_router)

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

@app.post("/run")
def run_code(submission: CodeSubmission, user: User = Depends(get_current_user)):
    # For now, we'll just run it in a container.
    # Logic: Write code to temp file -> Mount to Docker -> Run
    
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
