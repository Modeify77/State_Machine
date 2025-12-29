import os

import pytest

from engine import db


@pytest.fixture
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = str(tmp_path / "test.db")
    await db.init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


async def test_can_create_and_retrieve_agent(test_db):
    agent = await db.create_agent(db_path=test_db)
    assert "agent_id" in agent
    assert "claim_token" in agent  # Now returns claim_token, not token

    retrieved = await db.get_agent_by_id(agent["agent_id"], db_path=test_db)
    assert retrieved["agent_id"] == agent["agent_id"]


async def test_can_claim_agent(test_db):
    agent = await db.create_agent(db_path=test_db)

    claimed = await db.claim_agent(
        agent["agent_id"], agent["claim_token"], db_path=test_db
    )
    assert claimed is not None
    assert "token" in claimed
    assert claimed["agent_id"] == agent["agent_id"]


async def test_can_get_agent_by_token_after_claim(test_db):
    agent = await db.create_agent(db_path=test_db)

    # Claim first
    claimed = await db.claim_agent(
        agent["agent_id"], agent["claim_token"], db_path=test_db
    )

    # Now can get by token
    retrieved = await db.get_agent_by_token(claimed["token"], db_path=test_db)
    assert retrieved["agent_id"] == agent["agent_id"]


async def test_cannot_get_unclaimed_agent_by_token(test_db):
    agent = await db.create_agent(db_path=test_db)

    # Get raw token from DB (simulating a leak)
    async with db.get_db(test_db) as conn:
        cursor = await conn.execute(
            "SELECT token FROM agents WHERE agent_id = ?",
            (agent["agent_id"],)
        )
        row = await cursor.fetchone()
        raw_token = row[0]

    # Unclaimed token should not work
    retrieved = await db.get_agent_by_token(raw_token, db_path=test_db)
    assert retrieved is None


async def test_get_nonexistent_agent_returns_none(test_db):
    result = await db.get_agent_by_id("nonexistent", db_path=test_db)
    assert result is None


async def test_can_create_session(test_db):
    agent1 = await db.create_agent(db_path=test_db)
    agent2 = await db.create_agent(db_path=test_db)

    initial_state = {"fen": "starting", "turn": "white", "outcome": None}
    participants = {"white": agent1["agent_id"], "black": agent2["agent_id"]}

    session = await db.create_session(
        "chess.v1", initial_state, participants, db_path=test_db
    )

    assert session["status"] == "active"
    assert session["template"] == "chess.v1"
    assert session["tick"] == 0
    assert session["state"] == initial_state


async def test_can_get_session(test_db):
    agent1 = await db.create_agent(db_path=test_db)
    agent2 = await db.create_agent(db_path=test_db)

    initial_state = {"phase": "commit", "choices": {}, "result": None}
    participants = {"player_1": agent1["agent_id"], "player_2": agent2["agent_id"]}

    created = await db.create_session(
        "rps.v1", initial_state, participants, db_path=test_db
    )

    retrieved = await db.get_session(created["session_id"], db_path=test_db)
    assert retrieved["session_id"] == created["session_id"]
    assert retrieved["state"] == initial_state


async def test_can_update_session(test_db):
    agent1 = await db.create_agent(db_path=test_db)
    agent2 = await db.create_agent(db_path=test_db)

    initial_state = {"turn": "white"}
    participants = {"white": agent1["agent_id"], "black": agent2["agent_id"]}

    session = await db.create_session(
        "chess.v1", initial_state, participants, db_path=test_db
    )

    new_state = {"turn": "black"}
    updated = await db.update_session(
        session["session_id"], new_state, tick=1, db_path=test_db
    )

    assert updated["tick"] == 1
    assert updated["state"] == new_state


async def test_get_sessions_for_agent(test_db):
    agent1 = await db.create_agent(db_path=test_db)
    agent2 = await db.create_agent(db_path=test_db)
    agent3 = await db.create_agent(db_path=test_db)

    participants12 = {"white": agent1["agent_id"], "black": agent2["agent_id"]}
    await db.create_session("chess.v1", {}, participants12, db_path=test_db)

    participants23 = {"player_1": agent2["agent_id"], "player_2": agent3["agent_id"]}
    await db.create_session("rps.v1", {}, participants23, db_path=test_db)

    agent1_sessions = await db.get_sessions_for_agent(agent1["agent_id"], db_path=test_db)
    assert len(agent1_sessions) == 1

    agent2_sessions = await db.get_sessions_for_agent(agent2["agent_id"], db_path=test_db)
    assert len(agent2_sessions) == 2


async def test_get_participant(test_db):
    agent1 = await db.create_agent(db_path=test_db)
    agent2 = await db.create_agent(db_path=test_db)

    participants = {"white": agent1["agent_id"], "black": agent2["agent_id"]}
    session = await db.create_session("chess.v1", {}, participants, db_path=test_db)

    participant = await db.get_participant(
        session["session_id"], agent1["agent_id"], db_path=test_db
    )
    assert participant["role"] == "white"


async def test_get_participants(test_db):
    agent1 = await db.create_agent(db_path=test_db)
    agent2 = await db.create_agent(db_path=test_db)

    participants = {"white": agent1["agent_id"], "black": agent2["agent_id"]}
    session = await db.create_session("chess.v1", {}, participants, db_path=test_db)

    all_participants = await db.get_participants(session["session_id"], db_path=test_db)
    assert len(all_participants) == 2


async def test_log_and_get_actions(test_db):
    agent1 = await db.create_agent(db_path=test_db)
    agent2 = await db.create_agent(db_path=test_db)

    participants = {"white": agent1["agent_id"], "black": agent2["agent_id"]}
    session = await db.create_session("chess.v1", {}, participants, db_path=test_db)

    await db.log_action(
        session["session_id"], agent1["agent_id"], "white", "e2e4", 0, db_path=test_db
    )
    await db.log_action(
        session["session_id"], agent2["agent_id"], "black", "e7e5", 1, db_path=test_db
    )

    actions = await db.get_actions(session["session_id"], db_path=test_db)
    assert len(actions) == 2
    assert actions[0]["action"] == "e2e4"
    assert actions[0]["tick"] == 0
    assert actions[1]["action"] == "e7e5"
    assert actions[1]["tick"] == 1
