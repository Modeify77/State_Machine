from tests.conftest import create_and_claim_agent


async def test_create_session(client):
    # Create and claim two agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create session
    response = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": agent2["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "active"
    assert data["template"] == "test.v1"
    assert data["tick"] == 0
    assert "session_id" in data


async def test_non_participant_cannot_create(client):
    # Create and claim three agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)
    agent3 = await create_and_claim_agent(client)

    # Agent3 tries to create session for agent1 vs agent2
    response = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": agent2["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent3['token']}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_list_sessions_filters_by_participant(client):
    # Create and claim three agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)
    agent3 = await create_and_claim_agent(client)

    # Create session with agent1 and agent2
    await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": agent2["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    # Agent1 sees it
    resp_agent1 = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    assert resp_agent1.status_code == 200
    assert len(resp_agent1.json()["sessions"]) == 1

    # Agent2 sees it
    resp_agent2 = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {agent2['token']}"},
    )
    assert resp_agent2.status_code == 200
    assert len(resp_agent2.json()["sessions"]) == 1

    # Agent3 does not see it
    resp_agent3 = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {agent3['token']}"},
    )
    assert resp_agent3.status_code == 200
    assert len(resp_agent3.json()["sessions"]) == 0


async def test_create_session_unknown_template(client):
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    response = await client.post(
        "/sessions",
        json={
            "template": "unknown.v1",
            "participants": {"white": agent1["agent_id"], "black": agent2["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_create_session_missing_role(client):
    agent1 = await create_and_claim_agent(client)

    # Missing "black" role
    response = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_create_session_nonexistent_agent(client):
    agent1 = await create_and_claim_agent(client)

    response = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {
                "white": agent1["agent_id"],
                "black": "nonexistent-agent-id",
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# Join flow tests

async def test_create_session_with_open_slot(client):
    """Can create a session with an open slot for join-by-link."""
    agent1 = await create_and_claim_agent(client)

    response = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": None},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "waiting"
    assert data["join_url"] is not None
    assert data["session_id"] in data["join_url"]


async def test_join_open_session(client):
    """Friend can join a session with an open slot."""
    # Agent 1 creates session with open slot
    agent1 = await create_and_claim_agent(client)
    create_resp = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": None},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = create_resp.json()["session_id"]

    # Agent 2 registers and joins
    agent2 = await create_and_claim_agent(client)
    join_resp = await client.post(
        f"/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {agent2['token']}"},
    )

    assert join_resp.status_code == 200
    data = join_resp.json()
    assert data["role"] == "black"  # Gets the open slot
    assert data["status"] == "active"  # Session is now full


async def test_cannot_join_active_session(client):
    """Cannot join a session that is already active (full)."""
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)
    agent3 = await create_and_claim_agent(client)

    # Create full session
    create_resp = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": agent2["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = create_resp.json()["session_id"]

    # Agent 3 tries to join
    join_resp = await client.post(
        f"/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {agent3['token']}"},
    )

    assert join_resp.status_code == 400
    assert join_resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_cannot_join_twice(client):
    """Cannot join a session you're already in."""
    agent1 = await create_and_claim_agent(client)

    create_resp = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": None},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = create_resp.json()["session_id"]

    # Agent 1 tries to join their own session
    join_resp = await client.post(
        f"/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert join_resp.status_code == 400


async def test_get_session_state(client):
    """Can get current session state without making a move."""
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create session
    create_resp = await client.post(
        "/sessions",
        json={
            "template": "test.v1",
            "participants": {"white": agent1["agent_id"], "black": agent2["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = create_resp.json()["session_id"]

    # Get session state
    state_resp = await client.get(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert state_resp.status_code == 200
    data = state_resp.json()
    assert data["session_id"] == session_id
    assert data["status"] == "active"
    assert data["role"] == "white"
    assert "state" in data


async def test_get_session_shows_final_result(client):
    """Can see final game result after completion."""
    from engine.templates.registry import register_template, _templates
    from engine.templates.rps import RockPaperScissors

    if "rps.v1" not in _templates:
        register_template(RockPaperScissors())

    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create and complete game
    create_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {"player_1": agent1["agent_id"], "player_2": agent2["agent_id"]},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = create_resp.json()["session_id"]

    # Play to completion
    await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "rock"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "scissors"},
        headers={"Authorization": f"Bearer {agent2['token']}"},
    )

    # Both players can see final state
    p1_state = await client.get(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    p2_state = await client.get(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {agent2['token']}"},
    )

    assert p1_state.json()["status"] == "completed"
    assert p1_state.json()["state"]["result"] == "player_1_wins"
    assert p2_state.json()["state"]["result"] == "player_1_wins"


async def test_can_play_after_join(client):
    """After joining, both players can play the game."""
    from engine.templates.registry import register_template, _templates
    from engine.templates.rps import RockPaperScissors

    if "rps.v1" not in _templates:
        register_template(RockPaperScissors())

    # Agent 1 creates RPS session with open slot
    agent1 = await create_and_claim_agent(client)
    create_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {"player_1": agent1["agent_id"], "player_2": None},
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = create_resp.json()["session_id"]

    # Agent 2 joins
    agent2 = await create_and_claim_agent(client)
    await client.post(
        f"/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {agent2['token']}"},
    )

    # Both can play
    await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "rock"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    action_resp = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "scissors"},
        headers={"Authorization": f"Bearer {agent2['token']}"},
    )

    assert action_resp.status_code == 200
    assert action_resp.json()["status"] == "completed"
    assert action_resp.json()["state"]["result"] == "player_1_wins"
