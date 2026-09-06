"""
Learner Profile & Learning Event API Routes (Issue #23).

Endpoints:
- GET /me/learning-profile: Fetch own LEARNING.md and parsed structure
- PUT /me/learning-profile: Update own LEARNING.md with front matter validation
- POST /me/learning-profile/events: Record learning events (run_result, reset, lesson_opened)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import User, get_current_user
from learner_profile import (
    LearnerQuestionnaire,
    apply_questionnaire_profile,
    get_or_create_profile,
    get_user_progress,
    record_learner_event,
    update_profile_markdown,
)

router = APIRouter(prefix="/me", tags=["me"])


class LearningProfileResponse(BaseModel):
    markdown: str
    parsed: dict[str, Any]


class UpdateProfileRequest(BaseModel):
    markdown: str = Field(..., min_length=10, max_length=50_000)


class ProfileEventRequest(BaseModel):
    event_type: str = Field(..., min_length=2, max_length=50)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProfileEventResponse(BaseModel):
    success: bool
    profile: dict[str, Any]


class CourseProgress(BaseModel):
    course_slug: str
    resume_lesson: str | None = None
    resume_order: int | None = None
    resume_title: str | None = None
    completed_lessons: list[str] = Field(default_factory=list)
    completed: bool = False
    done_count: int = 0
    xp: int = 0
    lesson_count: int | None = None


class ProgressResponse(BaseModel):
    courses: list[CourseProgress]


@router.get("/progress", response_model=ProgressResponse)
def get_my_progress(user: User = Depends(get_current_user)):
    """Return per-course progress for the authenticated user (resume + completions)."""
    return ProgressResponse(courses=get_user_progress(user.username))


@router.get("/learning-profile", response_model=LearningProfileResponse)
def get_my_learning_profile(user: User = Depends(get_current_user)):
    """Fetch the authenticated user's living LEARNING.md profile."""
    markdown, parsed = get_or_create_profile(user.username)
    return LearningProfileResponse(markdown=markdown, parsed=parsed)


@router.put("/learning-profile", response_model=LearningProfileResponse)
def update_my_learning_profile(body: UpdateProfileRequest, user: User = Depends(get_current_user)):
    """Update the authenticated user's LEARNING.md profile with validation."""
    try:
        markdown, parsed = update_profile_markdown(user.username, body.markdown)
        return LearningProfileResponse(markdown=markdown, parsed=parsed)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to update profile: {str(exc)}"
        ) from exc


@router.post("/learning-profile/events", response_model=ProfileEventResponse)
def emit_learning_event(event: ProfileEventRequest, user: User = Depends(get_current_user)):
    """Emit a typed learner activity event to patch LEARNING.md."""
    try:
        updated_parsed = record_learner_event(
            username=user.username,
            event_type=event.event_type,
            payload=event.payload,
        )
        return ProfileEventResponse(success=True, profile=updated_parsed)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to record event: {str(exc)}") from exc


@router.post("/learning-profile/questionnaire", response_model=LearningProfileResponse)
def submit_learner_questionnaire(
    answers: LearnerQuestionnaire, user: User = Depends(get_current_user)
):
    """Calibrate learning profile using onboarding diagnostic questionnaire answers."""
    try:
        markdown, parsed = apply_questionnaire_profile(user.username, answers)
        return LearningProfileResponse(markdown=markdown, parsed=parsed)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to process questionnaire: {str(exc)}"
        ) from exc
