import os

import pytest
from httpx import ASGITransport, AsyncClient

import engine.db as db_module
from engine.db import init_db
from engine.templates.base import StateMachine
from engine.templates.registry import register_template, _templates


class TestTemplate(StateMachine):
    """Test template for session tests."""

    @property
    def template_id(self) -> str:
        return "test.v1"

    @property
    def roles(self) -> list[str]:
        return ["white", "black"]

    def initial_state(self) -> dict:
        return {"turn": "white", "moves": []}

    def legal_actions(self, state: dict, role: str) -> list[str]:
        if state["turn"] == role:
            return ["move"]
        return []

    def apply_action(self, state: dict, role: str, action: str) -> dict:
        new_state = state.copy()
        new_state["moves"] = state["moves"] + [action]
        new_state["turn"] = "black" if role == "white" else "white"
        return new_state

    def is_terminal(self, state: dict) -> bool:
        return len(state["moves"]) >= 10

    def view_state(self, state: dict, role: str) -> dict:
        return state.copy()


@pytest.fixture
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Patch the default database path for all db operations
    original_path = db_module.DATABASE_PATH
    db_module.DATABASE_PATH = db_path

    yield db_path

    db_module.DATABASE_PATH = original_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def test_template():
    """Register a test template and clean up after."""
    template = TestTemplate()
    register_template(template)
    yield template
    # Clean up
    if "test.v1" in _templates:
        del _templates["test.v1"]


@pytest.fixture
async def client(test_db, test_template):
    """Async test client with initialized test database and template."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
