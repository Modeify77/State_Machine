async def test_create_session(client):
    # Create two agents
    resp1 = await client.post("/agents")
    agent1 = resp1.json()

    resp2 = await client.post("/agents")
    agent2 = resp2.json()

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
    # Create three agents
    resp1 = await client.post("/agents")
    agent1 = resp1.json()

    resp2 = await client.post("/agents")
    agent2 = resp2.json()

    resp3 = await client.post("/agents")
    agent3 = resp3.json()

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
    # Create three agents
    resp1 = await client.post("/agents")
    agent1 = resp1.json()

    resp2 = await client.post("/agents")
    agent2 = resp2.json()

    resp3 = await client.post("/agents")
    agent3 = resp3.json()

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
    resp1 = await client.post("/agents")
    agent1 = resp1.json()

    resp2 = await client.post("/agents")
    agent2 = resp2.json()

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
    resp1 = await client.post("/agents")
    agent1 = resp1.json()

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
    resp1 = await client.post("/agents")
    agent1 = resp1.json()

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
