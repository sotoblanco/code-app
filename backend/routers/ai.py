from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ai_service import ai_service
from auth import get_current_admin, User

router = APIRouter(prefix="/ai", tags=["ai"])

class GenerateExerciseRequest(BaseModel):
    prompt: str

class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = ""

@router.post("/generate/exercise")
def generate_exercise(request: GenerateExerciseRequest, admin: User = Depends(get_current_admin)):
    result = ai_service.generate_exercise(request.prompt)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/discuss")
def discuss_implementation(request: ChatRequest, admin: User = Depends(get_current_admin)):
    response = ai_service.chat(request.message, request.context)
    return {"response": response}
