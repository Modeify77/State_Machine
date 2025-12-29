from tests.conftest import create_and_claim_agent


async def test_create_agent(client):
    response = await client.post("/agents")
    assert response.status_code == 201
    data = response.json()
    assert "agent_id" in data
    assert "claim_token" in data
    assert "token" not in data  # Token should NOT be returned on creation


async def test_claim_agent(client):
    # Create agent
    create_resp = await client.post("/agents")
    data = create_resp.json()
    agent_id = data["agent_id"]
    claim_token = data["claim_token"]

    # Claim the agent
    claim_resp = await client.post(
        f"/agents/{agent_id}/claim",
        json={"claim_token": claim_token},
    )
    assert claim_resp.status_code == 200
    claimed = claim_resp.json()
    assert "token" in claimed
    assert claimed["agent_id"] == agent_id


async def test_cannot_claim_twice(client):
    # Create and claim
    create_resp = await client.post("/agents")
    data = create_resp.json()
    agent_id = data["agent_id"]
    claim_token = data["claim_token"]

    # First claim succeeds
    await client.post(
        f"/agents/{agent_id}/claim",
        json={"claim_token": claim_token},
    )

    # Second claim fails
    second_claim = await client.post(
        f"/agents/{agent_id}/claim",
        json={"claim_token": claim_token},
    )
    assert second_claim.status_code == 400


async def test_wrong_claim_token_rejected(client):
    create_resp = await client.post("/agents")
    data = create_resp.json()
    agent_id = data["agent_id"]

    claim_resp = await client.post(
        f"/agents/{agent_id}/claim",
        json={"claim_token": "wrong-token"},
    )
    assert claim_resp.status_code == 400


async def test_token_authenticates(client):
    agent = await create_and_claim_agent(client)

    auth_resp = await client.get(
        "/sessions", headers={"Authorization": f"Bearer {agent['token']}"}
    )
    assert auth_resp.status_code == 200


async def test_unclaimed_token_does_not_authenticate(client, test_db):
    # Create but don't claim
    create_resp = await client.post("/agents")
    data = create_resp.json()

    # Try to authenticate with DB query to get raw token (simulating a leak)
    # This shouldn't work because agent isn't claimed
    import engine.db as db_module
    async with db_module.get_db(test_db) as db:
        cursor = await db.execute(
            "SELECT token FROM agents WHERE agent_id = ?",
            (data["agent_id"],)
        )
        row = await cursor.fetchone()
        raw_token = row[0]

    # Using unclaimed token should fail auth
    auth_resp = await client.get(
        "/sessions", headers={"Authorization": f"Bearer {raw_token}"}
    )
    assert auth_resp.status_code == 401
