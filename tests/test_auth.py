import pytest

from engine.db import create_agent, claim_agent


async def test_missing_token_returns_401(client):
    response = await client.get("/sessions")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_invalid_token_returns_401(client):
    response = await client.get(
        "/sessions", headers={"Authorization": "Bearer fake"}
    )
    assert response.status_code == 401


async def test_malformed_auth_header_returns_401(client):
    response = await client.get(
        "/sessions", headers={"Authorization": "InvalidFormat"}
    )
    assert response.status_code == 401


async def test_valid_token_proceeds(client, test_db):
    # Create agent
    agent = await create_agent(db_path=test_db)
    # Claim agent to get the token
    claimed = await claim_agent(
        agent["agent_id"], agent["claim_token"], db_path=test_db
    )
    token = claimed["token"]

    response = await client.get(
        "/sessions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code != 401
    assert response.status_code == 200
