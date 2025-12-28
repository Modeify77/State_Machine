from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import engine.db as db_module
from api.dependencies import get_current_agent
from api.schemas import CreateSessionRequest
from engine.errors import ForbiddenError, InvalidRequestError, NotFoundError
from engine.templates.registry import get_template

router = APIRouter()


@router.post("/sessions", status_code=201)
async def create_session(
    request: CreateSessionRequest,
    agent: dict = Depends(get_current_agent),
) -> JSONResponse:
    """Create a new game session."""
    # Get the template
    template = get_template(request.template)

    # Validate caller is one of the participants
    caller_id = agent["agent_id"]
    if caller_id not in request.participants.values():
        raise ForbiddenError("Caller must be a participant")

    # Validate all required roles are filled
    required_roles = set(template.roles)
    provided_roles = set(request.participants.keys())
    if required_roles != provided_roles:
        missing = required_roles - provided_roles
        extra = provided_roles - required_roles
        msg = []
        if missing:
            msg.append(f"missing roles: {missing}")
        if extra:
            msg.append(f"invalid roles: {extra}")
        raise InvalidRequestError(", ".join(msg))

    # Validate all agent_ids exist
    for role, agent_id in request.participants.items():
        existing = await db_module.get_agent_by_id(
            agent_id, db_path=db_module.DATABASE_PATH
        )
        if not existing:
            raise NotFoundError(f"Agent '{agent_id}' not found")

    # Create the session
    initial_state = template.initial_state()
    session = await db_module.create_session(
        template=request.template,
        initial_state=initial_state,
        participants=request.participants,
        db_path=db_module.DATABASE_PATH,
    )

    return JSONResponse(
        status_code=201,
        content={
            "session_id": session["session_id"],
            "template": session["template"],
            "status": session["status"],
            "tick": session["tick"],
        },
    )


@router.get("/sessions")
async def list_sessions(agent: dict = Depends(get_current_agent)) -> dict:
    """List sessions for the authenticated agent."""
    sessions = await db_module.get_sessions_for_agent(
        agent["agent_id"], db_path=db_module.DATABASE_PATH
    )

    return {
        "sessions": [
            {
                "session_id": s["session_id"],
                "template": s["template"],
                "status": s["status"],
                "tick": s["tick"],
            }
            for s in sessions
        ]
    }
