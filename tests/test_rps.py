import pytest

from engine.errors import AlreadyActedError, InvalidActionError
from engine.templates.rps import RockPaperScissors


@pytest.fixture
def rps():
    return RockPaperScissors()


def test_initial_state(rps):
    state = rps.initial_state()
    assert state["phase"] == "commit"
    assert state["choices"] == {"player_1": None, "player_2": None}
    assert state["result"] is None
    assert state["round"] == 1
    assert state["history"] == []


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


def test_both_commit_resolves_with_winner(rps):
    state = rps.initial_state()
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "scissors")
    assert state["phase"] == "reveal"
    assert state["result"] == "player_1_wins"


def test_terminal_after_winner(rps):
    state = {"phase": "reveal", "choices": {"player_1": "rock", "player_2": "scissors"}, "result": "player_1_wins"}
    assert rps.is_terminal(state) is True


def test_not_terminal_before_resolution(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    assert rps.is_terminal(state) is False


def test_no_actions_after_winner(rps):
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


def test_draw_resets_for_next_round(rps):
    """Draw should reset choices and increment round, not end game."""
    state = rps.initial_state()
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "rock")

    # Game should NOT be terminal
    assert rps.is_terminal(state) is False
    assert state["result"] is None
    assert state["phase"] == "commit"

    # Choices reset for next round
    assert state["choices"] == {"player_1": None, "player_2": None}

    # Round incremented
    assert state["round"] == 2

    # History records the draw
    assert len(state["history"]) == 1
    assert state["history"][0]["result"] == "draw"
    assert state["history"][0]["choices"] == {"player_1": "rock", "player_2": "rock"}


def test_draw_then_winner(rps):
    """After a draw, players can continue until someone wins."""
    state = rps.initial_state()

    # Round 1: Draw
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "rock")
    assert state["round"] == 2
    assert rps.is_terminal(state) is False

    # Round 2: Player 1 wins
    state = rps.apply_action(state, "player_1", "paper")
    state = rps.apply_action(state, "player_2", "rock")

    assert state["result"] == "player_1_wins"
    assert state["phase"] == "reveal"
    assert rps.is_terminal(state) is True
    assert len(state["history"]) == 1  # Only the draw is in history


def test_multiple_draws_then_winner(rps):
    """Game can have multiple draws before a winner."""
    state = rps.initial_state()

    # Round 1: Draw (rock vs rock)
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "rock")
    assert state["round"] == 2

    # Round 2: Draw (paper vs paper)
    state = rps.apply_action(state, "player_1", "paper")
    state = rps.apply_action(state, "player_2", "paper")
    assert state["round"] == 3

    # Round 3: Draw (scissors vs scissors)
    state = rps.apply_action(state, "player_1", "scissors")
    state = rps.apply_action(state, "player_2", "scissors")
    assert state["round"] == 4
    assert len(state["history"]) == 3

    # Round 4: Player 2 wins
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "paper")

    assert state["result"] == "player_2_wins"
    assert rps.is_terminal(state) is True
    assert len(state["history"]) == 3  # Three draws recorded


def test_can_act_after_draw(rps):
    """Players should be able to submit new choices after a draw."""
    state = rps.initial_state()

    # Round 1: Draw
    state = rps.apply_action(state, "player_1", "rock")
    state = rps.apply_action(state, "player_2", "rock")

    # Both players should have legal actions again
    assert set(rps.legal_actions(state, "player_1")) == {"rock", "paper", "scissors"}
    assert set(rps.legal_actions(state, "player_2")) == {"rock", "paper", "scissors"}


def test_apply_action_does_not_mutate_input(rps):
    state = rps.initial_state()
    original_state = {
        "phase": "commit",
        "choices": {"player_1": None, "player_2": None},
        "result": None,
        "round": 1,
        "history": [],
    }
    new_state = rps.apply_action(state, "player_1", "rock")
    assert state == original_state
    assert new_state != state


def test_already_acted_raises(rps):
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    with pytest.raises(AlreadyActedError):
        rps.apply_action(state, "player_1", "paper")  # Already committed


def test_invalid_action_raises(rps):
    state = {"phase": "commit", "choices": {"player_1": None, "player_2": None}, "result": None}
    with pytest.raises(InvalidActionError):
        rps.apply_action(state, "player_1", "invalid_choice")  # Not a valid choice


def test_template_id(rps):
    assert rps.template_id == "rps.v1"


def test_roles(rps):
    assert rps.roles == ["player_1", "player_2"]


def test_view_state_reveals_after_winner(rps):
    state = {"phase": "reveal", "choices": {"player_1": "rock", "player_2": "scissors"}, "result": "player_1_wins"}
    view = rps.view_state(state, "player_2")
    assert view["choices"]["player_1"] == "rock"
    assert view["choices"]["player_2"] == "scissors"
