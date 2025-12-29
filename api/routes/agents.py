from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import engine.db as db_module
from engine.errors import InvalidRequestError

router = APIRouter()


class ClaimRequest(BaseModel):
    claim_token: str


@router.post("/agents", status_code=201)
async def register_agent() -> JSONResponse:
    """Create a new agent. Returns agent_id and claim_token (NOT the bearer token)."""
    agent = await db_module.create_agent(db_path=db_module.DATABASE_PATH)
    return JSONResponse(
        status_code=201,
        content={"agent_id": agent["agent_id"], "claim_token": agent["claim_token"]},
    )


@router.post("/agents/{agent_id}/claim")
async def claim_agent(agent_id: str, request: ClaimRequest) -> JSONResponse:
    """Claim an agent's bearer token using the claim_token. One-time use."""
    result = await db_module.claim_agent(
        agent_id, request.claim_token, db_path=db_module.DATABASE_PATH
    )
    if not result:
        raise InvalidRequestError("Invalid or already claimed")
    return JSONResponse(
        status_code=200,
        content={"agent_id": result["agent_id"], "token": result["token"]},
    )
