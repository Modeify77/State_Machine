"""
MCP Server for State Machine Host.

Exposes game session tools and resources for real-time multiplayer coordination.

Run modes:
  python mcp_server.py              # stdio mode (for local Claude Code)
  python mcp_server.py --sse        # SSE mode on port 8080
  python mcp_server.py --sse --port 3000  # SSE mode on custom port

Environment variables:
  DATABASE_URL    PostgreSQL URL (e.g., postgresql://user:pass@host/db)
                  If not set, uses SQLite at ./state_machine.db
  MCP_HOST        Host to bind SSE server (default: 0.0.0.0)
  MCP_PORT        Port for SSE server (default: 8080)
"""

import argparse
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from weakref import WeakSet

from pydantic import AnyUrl
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from mcp.server.transport_security import TransportSecuritySettings

import engine.db as db_module
from engine.templates.registry import get_template, register_template, _templates
from engine.templates.rps import RockPaperScissors
from engine.templates.chess import Chess

# Ensure templates are registered
if "rps.v1" not in _templates:
    register_template(RockPaperScissors())
if "chess.v1" not in _templates:
    register_template(Chess())


# Track active MCP sessions watching each game session
# Maps game session_id -> WeakSet of ServerSession objects
# Using WeakSet so disconnected sessions are auto-cleaned
session_subscribers: dict[str, WeakSet[ServerSession]] = {}


def register_session_watcher(game_session_id: str, mcp_session: ServerSession) -> None:
    """Register an MCP client session as watching a game session."""
    if game_session_id not in session_subscribers:
        session_subscribers[game_session_id] = WeakSet()
    session_subscribers[game_session_id].add(mcp_session)
    print(f"[watch] Registered watcher for session {game_session_id} (total: {len(session_subscribers[game_session_id])})")


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize database on startup."""
    await db_module.init_db()
    yield


# Configure transport security to allow the Fly.io domain
# Get allowed hosts from environment or use defaults
allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS", "").split(",")
allowed_hosts = [h.strip() for h in allowed_hosts if h.strip()]

# Always allow localhost for local development
default_hosts = ["localhost", "127.0.0.1", "state-machine-mcp.fly.dev"]
all_allowed_hosts = list(set(default_hosts + allowed_hosts))

transport_security = TransportSecuritySettings(
    allowed_hosts=all_allowed_hosts,
    enable_dns_rebinding_protection=True,
)

mcp = FastMCP("State Machine", lifespan=lifespan, transport_security=transport_security)


# ============ TOOLS ============

@mcp.tool()
async def register_agent() -> dict:
    """
    Register a new agent with the system.

    Returns agent_id and claim_token. The claim_token must be exchanged
    for a bearer token using the claim_agent tool before the agent can act.

    Returns:
        agent_id: Unique identifier for this agent
        claim_token: One-time token to claim the bearer token
    """
    agent = await db_module.create_agent()
    return {
        "agent_id": agent["agent_id"],
        "claim_token": agent["claim_token"],
    }


@mcp.tool()
async def claim_agent(agent_id: str, claim_token: str) -> dict:
    """
    Claim an agent's bearer token using the claim_token.

    This is a one-time operation. After claiming, use the returned token
    for all authenticated operations.

    Args:
        agent_id: The agent ID from register_agent
        claim_token: The claim_token from register_agent

    Returns:
        agent_id: The agent ID
        token: Bearer token for authentication

    Raises error if claim_token is invalid or already claimed.
    """
    result = await db_module.claim_agent(agent_id, claim_token)
    if not result:
        return {"error": "Invalid claim token or already claimed"}
    return result


@mcp.tool()
async def create_session(
    token: str,
    template: str,
    participants: dict[str, str | None],
    ctx: Context = None,
) -> dict:
    """
    Create a new game session.

    Args:
        token: Your bearer token from claim_agent
        template: Game template ID (e.g., "rps.v1", "chess.v1")
        participants: Mapping of role -> agent_id. Use None for open slots.
                     Example: {"player_1": "your-agent-id", "player_2": None}

    Returns:
        session_id: Unique session identifier
        template: The template used
        status: "active" if full, "waiting" if has open slots
        tick: Current game tick (starts at 0)
        join_url: URL to share for joining (if has open slots)
    """
    # Validate token
    agent = await db_module.get_agent_by_token(token)
    if not agent:
        return {"error": "Invalid or unclaimed token"}

    # Get template
    try:
        tmpl = get_template(template)
    except Exception:
        return {"error": f"Unknown template: {template}"}

    # Validate caller is a participant
    filled = {k: v for k, v in participants.items() if v is not None}
    if agent["agent_id"] not in filled.values():
        return {"error": "Caller must be a participant"}

    # Validate roles match template
    required_roles = set(tmpl.roles)
    provided_roles = set(participants.keys())
    if required_roles != provided_roles:
        missing = required_roles - provided_roles
        extra = provided_roles - required_roles
        msg = []
        if missing:
            msg.append(f"missing roles: {missing}")
        if extra:
            msg.append(f"invalid roles: {extra}")
        return {"error": ", ".join(msg)}

    # Validate filled agent_ids exist
    for role, aid in filled.items():
        existing = await db_module.get_agent_by_id(aid)
        if not existing:
            return {"error": f"Agent '{aid}' not found"}

    # Determine status
    has_open = None in participants.values()
    status = "waiting" if has_open else "active"

    # Create session
    initial_state = tmpl.initial_state()
    session = await db_module.create_session(
        template=template,
        initial_state=initial_state,
        participants=filled,
        status=status,
    )

    # Register this MCP session as watching the game session
    if ctx and ctx.session:
        register_session_watcher(session["session_id"], ctx.session)

    return {
        "session_id": session["session_id"],
        "template": session["template"],
        "status": session["status"],
        "tick": session["tick"],
        "join_url": f"https://state-machine-mcp.fly.dev/join/{session['session_id']}" if has_open else None,
    }


@mcp.tool()
async def join_session(token: str, session_id: str, ctx: Context = None) -> dict:
    """
    Join a session with an open slot.

    Args:
        token: Your bearer token
        session_id: The session to join

    Returns:
        session_id: The session ID
        role: The role you were assigned
        status: New session status (may become "active")
        message: Confirmation message
    """
    # Validate token
    agent = await db_module.get_agent_by_token(token)
    if not agent:
        return {"error": "Invalid or unclaimed token"}

    # Get session
    session = await db_module.get_session(session_id)
    if not session:
        return {"error": f"Session '{session_id}' not found"}

    if session["status"] != "waiting":
        return {"error": "Session is not accepting new players"}

    # Get template and participants
    tmpl = get_template(session["template"])
    required_roles = set(tmpl.roles)
    participants = await db_module.get_participants(session_id)
    filled_roles = {p["role"] for p in participants}
    filled_agents = {p["agent_id"] for p in participants}

    # Check not already in session
    if agent["agent_id"] in filled_agents:
        return {"error": "Already a participant"}

    # Find open slot
    open_roles = required_roles - filled_roles
    if not open_roles:
        return {"error": "No open slots"}

    role = sorted(open_roles)[0]

    # Add participant
    await db_module.add_participant(session_id, agent["agent_id"], role)

    # Check if now full
    new_filled = filled_roles | {role}
    if new_filled == required_roles:
        await db_module.update_session(
            session_id,
            state=session["state"],
            tick=session["tick"],
            status="active",
        )
        new_status = "active"
        # Notify subscribers that session is now active
        await notify_session_change(session_id)
    else:
        new_status = "waiting"

    # Register this MCP session as watching the game session
    if ctx and ctx.session:
        register_session_watcher(session_id, ctx.session)

    return {
        "session_id": session_id,
        "role": role,
        "status": new_status,
        "message": f"Joined as {role}",
    }


@mcp.tool()
async def submit_action(token: str, session_id: str, action: str, ctx: Context = None) -> dict:
    """
    Submit an action to a game session.

    Args:
        token: Your bearer token
        session_id: The session ID
        action: The action to take (game-specific, e.g., "rock", "e2e4")

    Returns:
        tick: New tick after action
        status: Session status ("active", "completed", etc.)
        state: Your view of the game state (filtered by role)
    """
    # Validate token
    agent = await db_module.get_agent_by_token(token)
    if not agent:
        return {"error": "Invalid or unclaimed token"}

    # Get session
    session = await db_module.get_session(session_id)
    if not session:
        return {"error": f"Session '{session_id}' not found"}

    if session["status"] != "active":
        return {"error": f"Session is {session['status']}, not active"}

    # Get participant role
    participant = await db_module.get_participant(session_id, agent["agent_id"])
    if not participant:
        return {"error": "Not a participant"}

    role = participant["role"]

    # Get template and validate action
    tmpl = get_template(session["template"])

    if action not in tmpl.legal_actions(session["state"], role):
        return {"error": f"Invalid action: {action}"}

    # Apply action
    new_state = tmpl.apply_action(session["state"], role, action)
    new_status = "completed" if tmpl.is_terminal(new_state) else "active"
    new_tick = session["tick"] + 1

    # Update session
    await db_module.update_session(
        session_id,
        state=new_state,
        tick=new_tick,
        status=new_status,
    )

    # Log action
    await db_module.log_action(
        session_id,
        agent["agent_id"],
        role,
        action,
        session["tick"],
    )

    # Register this MCP session as watching the game session
    if ctx and ctx.session:
        register_session_watcher(session_id, ctx.session)

    # Notify subscribers of state change
    await notify_session_change(session_id)

    # Return role-filtered view
    view = tmpl.view_state(new_state, role)

    return {
        "tick": new_tick,
        "status": new_status,
        "state": view,
    }


@mcp.tool()
async def get_session_state(token: str, session_id: str, ctx: Context = None) -> dict:
    """
    Get current state of a game session without taking an action.

    Args:
        token: Your bearer token
        session_id: The session ID

    Returns:
        session_id: The session ID
        template: Game template
        status: Session status
        tick: Current tick
        role: Your role in the game
        state: Your view of the game state
    """
    # Validate token
    agent = await db_module.get_agent_by_token(token)
    if not agent:
        return {"error": "Invalid or unclaimed token"}

    # Get session
    session = await db_module.get_session(session_id)
    if not session:
        return {"error": f"Session '{session_id}' not found"}

    # Get participant role
    participant = await db_module.get_participant(session_id, agent["agent_id"])
    if not participant:
        return {"error": "Not a participant"}

    # Get filtered view
    tmpl = get_template(session["template"])
    view = tmpl.view_state(session["state"], participant["role"])

    # Register this MCP session as watching the game session
    if ctx and ctx.session:
        register_session_watcher(session_id, ctx.session)

    return {
        "session_id": session_id,
        "template": session["template"],
        "status": session["status"],
        "tick": session["tick"],
        "role": participant["role"],
        "state": view,
    }


@mcp.tool()
async def list_my_sessions(token: str) -> dict:
    """
    List all sessions where you are a participant.

    Args:
        token: Your bearer token

    Returns:
        sessions: List of session summaries
    """
    # Validate token
    agent = await db_module.get_agent_by_token(token)
    if not agent:
        return {"error": "Invalid or unclaimed token"}

    sessions = await db_module.get_sessions_for_agent(agent["agent_id"])

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


# ============ RESOURCES ============

@mcp.resource("session://{session_id}")
async def get_session_resource(session_id: str) -> str:
    """
    Get session state as a resource.

    This resource can be subscribed to for real-time updates.
    When any player makes a move, subscribers are notified.
    """
    session = await db_module.get_session(session_id)
    if not session:
        return f"Session {session_id} not found"

    # Return public info (no role filtering for resource view)
    return f"""Session: {session_id}
Template: {session['template']}
Status: {session['status']}
Tick: {session['tick']}
State: {session['state']}"""


async def notify_session_change(session_id: str):
    """Notify all subscribers that a session has changed."""
    if session_id not in session_subscribers:
        print(f"[notify] No watchers for session {session_id}")
        return

    uri = AnyUrl(f"session://{session_id}")

    # Notify all watching MCP sessions
    # WeakSet handles cleanup of dead sessions automatically
    watchers = list(session_subscribers[session_id])  # Copy to avoid mutation during iteration
    print(f"[notify] Sending update to {len(watchers)} watcher(s) for session {session_id}")
    for mcp_session in watchers:
        try:
            await mcp_session.send_resource_updated(uri)
            print(f"[notify] Sent notification for {uri}")
        except Exception as e:
            # Session may have disconnected - WeakSet will clean it up
            print(f"[notify] Failed to notify: {e}")


# ============ MAIN ============

def main():
    parser = argparse.ArgumentParser(description="MCP State Machine Server")
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Run in SSE mode (HTTP server) instead of stdio"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "0.0.0.0"),
        help="Host to bind SSE server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8080")),
        help="Port for SSE server (default: 8080)"
    )
    args = parser.parse_args()

    if args.sse:
        # Run as HTTP/SSE server for remote clients
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        from starlette.responses import HTMLResponse

        # Create join page HTML
        async def join_page(request):
            session_id = request.path_params.get("session_id", "")
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Join Game - State Machine</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               max-width: 600px; margin: 40px auto; padding: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d9ff; }}
        .step {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .step-num {{ background: #00d9ff; color: #1a1a2e; padding: 2px 10px; border-radius: 12px; font-weight: bold; }}
        code {{ background: #0f0f23; padding: 2px 6px; border-radius: 4px; }}
        pre {{ background: #0f0f23; padding: 15px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }}
        .copy-btn {{ background: #00d9ff; color: #1a1a2e; border: none; padding: 8px 16px;
                    border-radius: 4px; cursor: pointer; margin-top: 10px; }}
        .copy-btn:hover {{ background: #00b8d9; }}
        .magic-prompt {{ background: #0f3460; padding: 15px; border-radius: 8px; border-left: 4px solid #00d9ff; }}
        .claude-instructions {{ display: none; }}
    </style>
</head>
<body>
    <!--
    CLAUDE CODE INSTRUCTIONS:
    This is a game invite link. The session ID is: {session_id}

    If you have access to the state-machine MCP tools (register_agent, join_session, etc.):
    1. Use register_agent to create a player identity (if the user doesn't have one)
    2. Use claim_agent to get the bearer token
    3. Use join_session with token and session_id="{session_id}" to join the game
    4. Tell the user they've joined and explain how to play

    If you DON'T have access to state-machine MCP tools:
    Tell the user to add this to ~/.claude/mcp.json and restart Claude Code:
    {{"mcpServers": {{"state-machine": {{"type": "sse", "url": "https://state-machine-mcp.fly.dev/sse"}}}}}}
    -->

    <h1>🎮 You've been invited to play!</h1>
    <p>Someone wants to play a game with you using Claude Code.</p>

    <div class="step">
        <p><span class="step-num">1</span> <strong>First time?</strong> Add this to <code>~/.claude/mcp.json</code>:</p>
        <pre id="config">{{"mcpServers": {{"state-machine": {{"type": "sse", "url": "https://state-machine-mcp.fly.dev/sse"}}}}}}</pre>
        <button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('config').innerText)">Copy Config</button>
        <p style="margin-top:10px;opacity:0.7">Then restart Claude Code.</p>
    </div>

    <div class="step">
        <p><span class="step-num">2</span> <strong>Paste this link into Claude Code:</strong></p>
        <div class="magic-prompt">
            <pre id="prompt">https://state-machine-mcp.fly.dev/join/{session_id}</pre>
            <button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('prompt').innerText)">Copy Link</button>
        </div>
        <p style="margin-top:10px;opacity:0.7">Claude will automatically join the game!</p>
    </div>

    <div class="step">
        <p><span class="step-num">3</span> <strong>Play!</strong> Just tell Claude your move (rock, paper, or scissors)</p>
    </div>

    <p style="opacity:0.5;margin-top:30px">Session: {session_id}</p>
</body>
</html>"""
            return HTMLResponse(html)

        # Mount both the MCP SSE app and our join pages
        app = Starlette(routes=[
            Route("/join/{session_id}", join_page),
            Mount("/", app=mcp.sse_app()),
        ])

        print(f"Starting MCP server in SSE mode on {args.host}:{args.port}")
        print(f"MCP endpoint: http://{args.host}:{args.port}/sse")
        print(f"Join pages: http://{args.host}:{args.port}/join/<session_id>")
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    else:
        # Run via stdio for local Claude Code
        mcp.run()


if __name__ == "__main__":
    main()
