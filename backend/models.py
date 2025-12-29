from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr

class CourseBase(SQLModel):
    title: str
    description: str
    slug: str = Field(index=True, unique=True)
    is_published: bool = False

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(unique=True, index=True)
    role: str = Field(default="student")

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int

class Token(SQLModel):
    access_token: str
    token_type: str

class TokenData(SQLModel):
    username: Optional[str] = None
    role: Optional[str] = None

class Course(CourseBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exercises: List["Exercise"] = Relationship(back_populates="course")

class ExerciseBase(SQLModel):
    title: str
    slug: str = Field(index=True)
    description: str  # Markdown content
    initial_code: str
    test_code: str
    order: int = 0
    course_id: Optional[int] = Field(default=None, foreign_key="course.id")

class Exercise(ExerciseBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course: Optional[Course] = Relationship(back_populates="exercises")

class CourseCreate(CourseBase):
    pass

class CourseRead(CourseBase):
    id: int
    exercises: List["ExerciseRead"] = []

class ExerciseCreate(ExerciseBase):
    pass

class ExerciseRead(ExerciseBase):
    id: int

# Update forward refs
CourseRead.update_forward_refs()
