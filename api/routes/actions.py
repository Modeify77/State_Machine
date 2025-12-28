from fastapi import APIRouter, Depends

import engine.db as db_module
from api.dependencies import get_current_agent
from api.schemas import SubmitActionRequest
from engine.errors import ConflictError, ForbiddenError, InvalidActionError, NotFoundError
from engine.templates.registry import get_template

router = APIRouter()


@router.post("/sessions/{session_id}/actions")
async def submit_action(
    session_id: str,
    request: SubmitActionRequest,
    agent: dict = Depends(get_current_agent),
) -> dict:
    """Submit an action to a session."""
    # Get the session
    session = await db_module.get_session(session_id, db_path=db_module.DATABASE_PATH)
    if not session:
        raise NotFoundError(f"Session '{session_id}' not found")

    # Check session is active
    if session["status"] != "active":
        raise InvalidActionError("Session is not active")

    # Validate agent is a participant and get their role
    participant = await db_module.get_participant(
        session_id, agent["agent_id"], db_path=db_module.DATABASE_PATH
    )
    if not participant:
        raise ForbiddenError("Not a participant in this session")

    role = participant["role"]

    # Get the template
    template = get_template(session["template"])

    # For sequential games, validate expected_tick if provided
    if request.expected_tick is not None:
        if request.expected_tick != session["tick"]:
            raise ConflictError(
                f"Tick mismatch: expected {request.expected_tick}, current is {session['tick']}"
            )

    # Check if action is legal before applying
    legal = template.legal_actions(session["state"], role)
    if request.action not in legal:
        # Let apply_action raise the appropriate error (InvalidActionError or AlreadyActedError)
        # This will give a more specific error message
        pass

    # Apply the action (template will validate and may raise errors)
    new_state = template.apply_action(session["state"], role, request.action)

    # Determine new status
    new_status = "completed" if template.is_terminal(new_state) else "active"
    new_tick = session["tick"] + 1

    # Update the session
    await db_module.update_session(
        session_id,
        state=new_state,
        tick=new_tick,
        status=new_status,
        db_path=db_module.DATABASE_PATH,
    )

    # Log the action
    await db_module.log_action(
        session_id=session_id,
        agent_id=agent["agent_id"],
        role=role,
        action=request.action,
        tick=session["tick"],
        db_path=db_module.DATABASE_PATH,
    )

    # Return the new state (filtered for this role)
    view = template.view_state(new_state, role)

    return {
        "tick": new_tick,
        "status": new_status,
        "state": view,
    }
