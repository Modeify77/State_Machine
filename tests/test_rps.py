import pytest

from engine.errors import InvalidActionError
from engine.templates.rps import RockPaperScissors


@pytest.fixture
def rps():
    return RockPaperScissors()


def test_initial_state(rps):
    state = rps.initial_state()
    assert state["phase"] == "commit"
    assert state["choices"] == {"player_1": None, "player_2": None}
    assert state["result"] is None


def test_legal_actions_during_commit(rps):
    state = {"phase": "commit", "choices": {"player_1": None, "player_2": None}, "result": None}
    actions = rps.legal_actions(state, "player_1")
    assert set(actions) == {"rock", "paper", "scissors"}


def test_no_actions_after_committed(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    actions = rps.legal_actions(state, "player_1")
    assert actions == []


def test_player_2_can_still_act_after_player_1_commits(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    actions = rps.legal_actions(state, "player_2")
    assert set(actions) == {"rock", "paper", "scissors"}


def test_view_state_hides_opponent_choice(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    view = rps.view_state(state, "player_2")
    assert view["choices"]["player_1"] == "hidden"
    assert view["choices"]["player_2"] is None


def test_view_state_shows_own_choice(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    view = rps.view_state(state, "player_1")
    assert view["choices"]["player_1"] == "rock"
    assert view["choices"]["player_2"] is None


def test_both_commit_resolves(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    state = rps.apply_action(state, "player_2", "scissors")
    assert state["phase"] == "reveal"
    assert state["result"] == "player_1_wins"


def test_terminal_after_resolution(rps):
    state = {"phase": "reveal", "choices": {"player_1": "rock", "player_2": "scissors"}, "result": "player_1_wins"}
    assert rps.is_terminal(state) is True


def test_not_terminal_before_resolution(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    assert rps.is_terminal(state) is False


def test_no_actions_after_reveal(rps):
    state = {"phase": "reveal", "choices": {"player_1": "rock", "player_2": "scissors"}, "result": "player_1_wins"}
    assert rps.legal_actions(state, "player_1") == []
    assert rps.legal_actions(state, "player_2") == []


def test_rock_beats_scissors(rps):
    state = rps.initial_state()
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "scissors")
    assert state["result"] == "player_1_wins"


def test_scissors_beats_paper(rps):
    state = rps.initial_state()
    state = rps.apply_action(state, "player_1", "scissors")
    state = rps.apply_action(state, "player_2", "paper")
    assert state["result"] == "player_1_wins"


def test_paper_beats_rock(rps):
    state = rps.initial_state()
    state = rps.apply_action(state, "player_1", "paper")
    state = rps.apply_action(state, "player_2", "rock")
    assert state["result"] == "player_1_wins"


def test_player_2_wins(rps):
    state = rps.initial_state()
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "paper")
    assert state["result"] == "player_2_wins"


def test_draw(rps):
    state = rps.initial_state()
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "rock")
    assert state["result"] == "draw"


def test_apply_action_does_not_mutate_input(rps):
    state = rps.initial_state()
    original_state = {"phase": "commit", "choices": {"player_1": None, "player_2": None}, "result": None}
    new_state = rps.apply_action(state, "player_1", "rock")
    assert state == original_state
    assert new_state != state


def test_illegal_action_raises(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    with pytest.raises(InvalidActionError):
        rps.apply_action(state, "player_1", "paper")  # Already committed


def test_template_id(rps):
    assert rps.template_id == "rps.v1"


def test_roles(rps):
    assert rps.roles == ["player_1", "player_2"]


def test_view_state_reveals_after_resolution(rps):
    state = {"phase": "reveal", "choices": {"player_1": "rock", "player_2": "scissors"}, "result": "player_1_wins"}
    view = rps.view_state(state, "player_2")
    assert view["choices"]["player_1"] == "rock"
    assert view["choices"]["player_2"] == "scissors"
