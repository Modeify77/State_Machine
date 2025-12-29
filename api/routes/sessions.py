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
    """Create a new game session. Supports open slots (None) for join-by-link."""
    # Get the template
    template = get_template(request.template)

    # Validate caller is one of the filled participants
    caller_id = agent["agent_id"]
    filled_participants = {k: v for k, v in request.participants.items() if v is not None}
    if caller_id not in filled_participants.values():
        raise ForbiddenError("Caller must be a participant")

    # Validate all required roles are specified (can be None for open slots)
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

    # Validate filled agent_ids exist
    for role, agent_id in filled_participants.items():
        existing = await db_module.get_agent_by_id(
            agent_id, db_path=db_module.DATABASE_PATH
        )
        if not existing:
            raise NotFoundError(f"Agent '{agent_id}' not found")

    # Determine initial status (waiting if open slots, active if full)
    has_open_slots = None in request.participants.values()
    initial_status = "waiting" if has_open_slots else "active"

    # Create the session
    initial_state = template.initial_state()
    session = await db_module.create_session(
        template=request.template,
        initial_state=initial_state,
        participants=filled_participants,  # Only store filled slots
        status=initial_status,
        db_path=db_module.DATABASE_PATH,
    )

    # Build join link for sharing
    join_url = f"/sessions/{session['session_id']}/join"

    return JSONResponse(
        status_code=201,
        content={
            "session_id": session["session_id"],
            "template": session["template"],
            "status": session["status"],
            "tick": session["tick"],
            "join_url": join_url if has_open_slots else None,
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


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    agent: dict = Depends(get_current_agent),
) -> JSONResponse:
    """Get current session state (filtered by role)."""
    # Get the session
    session = await db_module.get_session(session_id, db_path=db_module.DATABASE_PATH)
    if not session:
        raise NotFoundError(f"Session '{session_id}' not found")

    # Check agent is a participant
    participant = await db_module.get_participant(
        session_id, agent["agent_id"], db_path=db_module.DATABASE_PATH
    )
    if not participant:
        raise ForbiddenError("Not a participant in this session")

    # Get template for view_state filtering
    template = get_template(session["template"])
    view = template.view_state(session["state"], participant["role"])

    return JSONResponse(
        status_code=200,
        content={
            "session_id": session_id,
            "template": session["template"],
            "status": session["status"],
            "tick": session["tick"],
            "role": participant["role"],
            "state": view,
        },
    )


@router.post("/sessions/{session_id}/join")
async def join_session(
    session_id: str,
    agent: dict = Depends(get_current_agent),
) -> JSONResponse:
    """Join a session with an open slot."""
    # Get the session
    session = await db_module.get_session(session_id, db_path=db_module.DATABASE_PATH)
    if not session:
        raise NotFoundError(f"Session '{session_id}' not found")

    # Must be waiting for players
    if session["status"] != "waiting":
        raise InvalidRequestError("Session is not accepting new players")

    # Get template to know required roles
    template = get_template(session["template"])
    required_roles = set(template.roles)

    # Get current participants
    participants = await db_module.get_participants(
        session_id, db_path=db_module.DATABASE_PATH
    )
    filled_roles = {p["role"] for p in participants}
    filled_agents = {p["agent_id"] for p in participants}

    # Check caller isn't already in the session
    if agent["agent_id"] in filled_agents:
        raise InvalidRequestError("Already a participant in this session")

    # Find open slot
    open_roles = required_roles - filled_roles
    if not open_roles:
        raise InvalidRequestError("No open slots available")

    # Take the first open role (or could let caller specify)
    role = sorted(open_roles)[0]

    # Add the participant
    await db_module.add_participant(
        session_id, agent["agent_id"], role, db_path=db_module.DATABASE_PATH
    )

    # Check if session is now full -> activate it
    new_filled_roles = filled_roles | {role}
    if new_filled_roles == required_roles:
        await db_module.update_session(
            session_id,
            state=session["state"],
            tick=session["tick"],
            status="active",
            db_path=db_module.DATABASE_PATH,
        )
        new_status = "active"
    else:
        new_status = "waiting"

    return JSONResponse(
        status_code=200,
        content={
            "session_id": session_id,
            "role": role,
            "status": new_status,
            "message": f"Joined as {role}",
        },
    )
