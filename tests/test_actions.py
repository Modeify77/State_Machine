import pytest

from engine.templates.registry import register_template, _templates
from engine.templates.rps import RockPaperScissors
from tests.conftest import create_and_claim_agent


@pytest.fixture
def rps_template():
    """Ensure RPS template is registered."""
    if "rps.v1" not in _templates:
        register_template(RockPaperScissors())
    yield
    # Don't clean up - it's a built-in template


async def test_submit_valid_action_rps(client, rps_template):
    # Create and claim two agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create RPS session
    session_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {
                "player_1": agent1["agent_id"],
                "player_2": agent2["agent_id"],
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = session_resp.json()["session_id"]

    # Player 1 submits rock
    response = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "rock"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tick"] == 1
    assert data["status"] == "active"  # Not terminal yet


async def test_both_players_complete_game(client, rps_template):
    # Create and claim two agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create RPS session
    session_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {
                "player_1": agent1["agent_id"],
                "player_2": agent2["agent_id"],
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = session_resp.json()["session_id"]

    # Player 1 submits rock
    await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "rock"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    # Player 2 submits scissors
    response = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "scissors"},
        headers={"Authorization": f"Bearer {agent2['token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tick"] == 2
    assert data["status"] == "completed"
    assert data["state"]["result"] == "player_1_wins"


async def test_already_acted_rejected_rps(client, rps_template):
    # Create and claim two agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create RPS session
    session_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {
                "player_1": agent1["agent_id"],
                "player_2": agent2["agent_id"],
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = session_resp.json()["session_id"]

    # Player 1 submits rock
    await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "rock"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    # Player 1 tries to submit again
    response = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "paper"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ALREADY_ACTED"


async def test_tick_mismatch_rejected(client, rps_template):
    # Create and claim two agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create RPS session
    session_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {
                "player_1": agent1["agent_id"],
                "player_2": agent2["agent_id"],
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = session_resp.json()["session_id"]

    # Submit with wrong expected_tick
    response = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "rock", "expected_tick": 5},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_non_participant_rejected(client, rps_template):
    # Create and claim three agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)
    agent3 = await create_and_claim_agent(client)

    # Create RPS session with agent1 and agent2
    session_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {
                "player_1": agent1["agent_id"],
                "player_2": agent2["agent_id"],
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = session_resp.json()["session_id"]

    # Agent3 tries to submit action
    response = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "rock"},
        headers={"Authorization": f"Bearer {agent3['token']}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_invalid_action_rejected(client, rps_template):
    # Create and claim two agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create RPS session
    session_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {
                "player_1": agent1["agent_id"],
                "player_2": agent2["agent_id"],
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = session_resp.json()["session_id"]

    # Submit invalid action
    response = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "invalid_move"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ACTION"


async def test_action_on_completed_session_rejected(client, rps_template):
    # Create and claim two agents
    agent1 = await create_and_claim_agent(client)
    agent2 = await create_and_claim_agent(client)

    # Create RPS session
    session_resp = await client.post(
        "/sessions",
        json={
            "template": "rps.v1",
            "participants": {
                "player_1": agent1["agent_id"],
                "player_2": agent2["agent_id"],
            },
        },
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )
    session_id = session_resp.json()["session_id"]

    # Complete the game
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

    # Try to act on completed session
    response = await client.post(
        f"/sessions/{session_id}/actions",
        json={"action": "paper"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ACTION"


async def test_session_not_found(client, rps_template):
    agent1 = await create_and_claim_agent(client)

    response = await client.post(
        "/sessions/nonexistent-session-id/actions",
        json={"action": "rock"},
        headers={"Authorization": f"Bearer {agent1['token']}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
