async def test_create_agent(client):
    response = await client.post("/agents")
    assert response.status_code == 201
    data = response.json()
    assert "agent_id" in data
    assert "token" in data


async def test_token_authenticates(client):
    create_resp = await client.post("/agents")
    token = create_resp.json()["token"]

    auth_resp = await client.get(
        "/sessions", headers={"Authorization": f"Bearer {token}"}
    )
    assert auth_resp.status_code != 401
    assert auth_resp.status_code == 200
