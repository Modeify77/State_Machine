from fastapi import APIRouter
from fastapi.responses import JSONResponse

import engine.db as db_module

router = APIRouter()


@router.post("/agents", status_code=201)
async def register_agent() -> JSONResponse:
    """Create a new agent with random ID and token."""
    agent = await db_module.create_agent(db_path=db_module.DATABASE_PATH)
    return JSONResponse(
        status_code=201,
        content={"agent_id": agent["agent_id"], "token": agent["token"]},
    )
