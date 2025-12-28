import pytest

from engine.errors import NotFoundError
from engine.templates.base import StateMachine
from engine.templates.registry import get_template, list_templates, register_template


class DummyTemplate(StateMachine):
    """Minimal dummy implementation for testing."""

    @property
    def template_id(self) -> str:
        return "dummy.v1"

    @property
    def roles(self) -> list[str]:
        return ["player_1", "player_2"]

    def initial_state(self) -> dict:
        return {"turn": "player_1", "value": 0}

    def legal_actions(self, state: dict, role: str) -> list[str]:
        if state["turn"] == role:
            return ["increment", "decrement"]
        return []

    def apply_action(self, state: dict, role: str, action: str) -> dict:
        new_state = state.copy()
        if action == "increment":
            new_state["value"] += 1
        elif action == "decrement":
            new_state["value"] -= 1
        new_state["turn"] = "player_2" if role == "player_1" else "player_1"
        return new_state

    def is_terminal(self, state: dict) -> bool:
        return abs(state["value"]) >= 3

    def view_state(self, state: dict, role: str) -> dict:
        return state.copy()


def test_dummy_template_conforms_to_interface():
    template = DummyTemplate()

    # Verify properties return correct types
    assert isinstance(template.template_id, str)
    assert template.template_id == "dummy.v1"

    assert isinstance(template.roles, list)
    assert all(isinstance(r, str) for r in template.roles)
    assert template.roles == ["player_1", "player_2"]

    # Verify initial_state returns dict
    state = template.initial_state()
    assert isinstance(state, dict)

    # Verify legal_actions returns list of strings
    actions = template.legal_actions(state, "player_1")
    assert isinstance(actions, list)
    assert all(isinstance(a, str) for a in actions)

    # Verify apply_action returns new dict
    new_state = template.apply_action(state, "player_1", "increment")
    assert isinstance(new_state, dict)
    assert new_state != state  # Should be different

    # Verify is_terminal returns bool
    assert isinstance(template.is_terminal(state), bool)
    assert template.is_terminal(state) is False

    # Verify view_state returns dict
    view = template.view_state(state, "player_1")
    assert isinstance(view, dict)


def test_template_registry():
    template = DummyTemplate()
    register_template(template)

    # Verify lookup works
    retrieved = get_template("dummy.v1")
    assert retrieved is template
    assert retrieved.template_id == "dummy.v1"

    # Verify list_templates includes it
    assert "dummy.v1" in list_templates()


def test_get_unknown_template_raises():
    with pytest.raises(NotFoundError) as exc_info:
        get_template("nonexistent.v1")
    assert "nonexistent.v1" in str(exc_info.value)
