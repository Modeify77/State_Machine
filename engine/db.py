import json
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

DATABASE_PATH = "state_machine.db"


async def init_db(db_path: str = DATABASE_PATH) -> None:
    """Initialize the database with schema."""
    schema_path = Path(__file__).parent.parent / "schema.sql"
    schema = schema_path.read_text()

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(schema)
        await db.commit()


@asynccontextmanager
async def get_db(db_path: str = DATABASE_PATH):
    """Async context manager for database connections."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# Agent helpers

async def create_agent(db_path: str = DATABASE_PATH) -> dict:
    """Create a new agent with random ID, token, and claim_token."""
    agent_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    claim_token = secrets.token_urlsafe(16)

    async with get_db(db_path) as db:
        await db.execute(
            "INSERT INTO agents (agent_id, token, claim_token) VALUES (?, ?, ?)",
            (agent_id, token, claim_token)
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT agent_id, claim_token, created_at FROM agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def get_agent_by_id(agent_id: str, db_path: str = DATABASE_PATH) -> dict | None:
    """Retrieve an agent by ID."""
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT agent_id, token, created_at FROM agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_agent_by_token(token: str, db_path: str = DATABASE_PATH) -> dict | None:
    """Retrieve an agent by token (only if claimed)."""
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT agent_id, token, created_at FROM agents WHERE token = ? AND claimed = 1",
            (token,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def claim_agent(agent_id: str, claim_token: str, db_path: str = DATABASE_PATH) -> dict | None:
    """Claim an agent's token using the claim_token. Returns token if successful, None if already claimed or invalid."""
    async with get_db(db_path) as db:
        # Check if agent exists and hasn't been claimed
        cursor = await db.execute(
            "SELECT agent_id, token, claim_token, claimed FROM agents WHERE agent_id = ?",
            (agent_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None  # Agent doesn't exist

        agent = dict(row)

        if agent["claimed"]:
            return None  # Already claimed

        if agent["claim_token"] != claim_token:
            return None  # Invalid claim token

        # Mark as claimed
        await db.execute(
            "UPDATE agents SET claimed = 1 WHERE agent_id = ?",
            (agent_id,)
        )
        await db.commit()

        return {"agent_id": agent_id, "token": agent["token"]}


# Session helpers

async def create_session(
    template: str,
    initial_state: dict,
    participants: dict[str, str],
    status: str = "active",
    db_path: str = DATABASE_PATH
) -> dict:
    """Create a new session with participants.

    Args:
        template: Template ID (e.g., "chess.v1")
        initial_state: Initial game state dict
        participants: Mapping of role -> agent_id
        status: Initial status ("active" or "waiting" for open slots)

    Returns:
        Session dict with session_id, template, state, status, tick, timestamps
    """
    session_id = str(uuid.uuid4())
    state_json = json.dumps(initial_state)

    async with get_db(db_path) as db:
        await db.execute(
            """INSERT INTO sessions (session_id, template, state, status, tick)
               VALUES (?, ?, ?, ?, 0)""",
            (session_id, template, state_json, status)
        )

        for role, agent_id in participants.items():
            await db.execute(
                "INSERT INTO participants (session_id, agent_id, role) VALUES (?, ?, ?)",
                (session_id, agent_id, role)
            )

        await db.commit()

        cursor = await db.execute(
            """SELECT session_id, template, state, status, tick, created_at, updated_at
               FROM sessions WHERE session_id = ?""",
            (session_id,)
        )
        row = await cursor.fetchone()
        result = dict(row)
        result["state"] = json.loads(result["state"])
        return result


async def get_session(session_id: str, db_path: str = DATABASE_PATH) -> dict | None:
    """Retrieve a session by ID."""
    async with get_db(db_path) as db:
        cursor = await db.execute(
            """SELECT session_id, template, state, status, tick, created_at, updated_at
               FROM sessions WHERE session_id = ?""",
            (session_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["state"] = json.loads(result["state"])
        return result


async def update_session(
    session_id: str,
    state: dict,
    tick: int,
    status: str = "active",
    db_path: str = DATABASE_PATH
) -> dict:
    """Update session state and tick."""
    state_json = json.dumps(state)

    async with get_db(db_path) as db:
        await db.execute(
            """UPDATE sessions
               SET state = ?, tick = ?, status = ?, updated_at = datetime('now')
               WHERE session_id = ?""",
            (state_json, tick, status, session_id)
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT session_id, template, state, status, tick, created_at, updated_at
               FROM sessions WHERE session_id = ?""",
            (session_id,)
        )
        row = await cursor.fetchone()
        result = dict(row)
        result["state"] = json.loads(result["state"])
        return result


async def get_sessions_for_agent(agent_id: str, db_path: str = DATABASE_PATH) -> list[dict]:
    """Get all sessions where agent is a participant."""
    async with get_db(db_path) as db:
        cursor = await db.execute(
            """SELECT s.session_id, s.template, s.state, s.status, s.tick,
                      s.created_at, s.updated_at
               FROM sessions s
               JOIN participants p ON s.session_id = p.session_id
               WHERE p.agent_id = ?
               ORDER BY s.created_at DESC""",
            (agent_id,)
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            result["state"] = json.loads(result["state"])
            results.append(result)
        return results


# Participant helpers

async def get_participant(
    session_id: str,
    agent_id: str,
    db_path: str = DATABASE_PATH
) -> dict | None:
    """Get participant info for an agent in a session."""
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT session_id, agent_id, role FROM participants WHERE session_id = ? AND agent_id = ?",
            (session_id, agent_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_participants(session_id: str, db_path: str = DATABASE_PATH) -> list[dict]:
    """Get all participants for a session."""
    async with get_db(db_path) as db:
        cursor = await db.execute(
            "SELECT session_id, agent_id, role FROM participants WHERE session_id = ?",
            (session_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def add_participant(
    session_id: str,
    agent_id: str,
    role: str,
    db_path: str = DATABASE_PATH
) -> dict:
    """Add a participant to a session (for join flow)."""
    async with get_db(db_path) as db:
        await db.execute(
            "INSERT INTO participants (session_id, agent_id, role) VALUES (?, ?, ?)",
            (session_id, agent_id, role)
        )
        await db.commit()
        return {"session_id": session_id, "agent_id": agent_id, "role": role}


# Action helpers

async def log_action(
    session_id: str,
    agent_id: str,
    role: str,
    action: str,
    tick: int,
    db_path: str = DATABASE_PATH
) -> dict:
    """Log an action to the immutable action log."""
    action_id = str(uuid.uuid4())

    async with get_db(db_path) as db:
        await db.execute(
            """INSERT INTO actions (action_id, session_id, agent_id, role, action, tick)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (action_id, session_id, agent_id, role, action, tick)
        )
        await db.commit()

        cursor = await db.execute(
            """SELECT action_id, session_id, agent_id, role, action, tick, created_at
               FROM actions WHERE action_id = ?""",
            (action_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def get_actions(session_id: str, db_path: str = DATABASE_PATH) -> list[dict]:
    """Get all actions for a session, ordered by tick."""
    async with get_db(db_path) as db:
        cursor = await db.execute(
            """SELECT action_id, session_id, agent_id, role, action, tick, created_at
               FROM actions WHERE session_id = ?
               ORDER BY tick, created_at""",
            (session_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
