from fastapi import APIRouter, Depends

from api.dependencies import get_current_agent

router = APIRouter()


@router.get("/sessions")
async def list_sessions(agent: dict = Depends(get_current_agent)) -> dict:
    """List sessions for the authenticated agent."""
    return {"sessions": []}
