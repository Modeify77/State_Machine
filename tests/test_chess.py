import pytest

from engine.errors import InvalidActionError
from engine.templates.chess import Chess


@pytest.fixture
def chess():
    return Chess()


def test_template_id(chess):
    assert chess.template_id == "chess.v1"


def test_roles(chess):
    assert chess.roles == ["white", "black"]


def test_initial_state(chess):
    state = chess.initial_state()
    assert state["result"] is None
    assert state["moves"] == []
    # Standard starting FEN
    assert "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR" in state["fen"]


def test_white_moves_first(chess):
    state = chess.initial_state()
    white_actions = chess.legal_actions(state, "white")
    black_actions = chess.legal_actions(state, "black")

    assert len(white_actions) > 0  # White has moves
    assert black_actions == []  # Black cannot move yet


def test_legal_actions_returns_uci(chess):
    state = chess.initial_state()
    actions = chess.legal_actions(state, "white")
    # Should include standard opening moves in UCI notation
    assert "e2e4" in actions
    assert "d2d4" in actions
    assert "g1f3" in actions


def test_apply_action_valid_move(chess):
    state = chess.initial_state()
    new_state = chess.apply_action(state, "white", "e2e4")

    assert "e2e4" in new_state["moves"]
    assert new_state["fen"] != state["fen"]
    assert new_state["result"] is None


def test_apply_action_not_your_turn(chess):
    state = chess.initial_state()
    with pytest.raises(InvalidActionError, match="Not your turn"):
        chess.apply_action(state, "black", "e7e5")


def test_apply_action_illegal_move(chess):
    state = chess.initial_state()
    with pytest.raises(InvalidActionError, match="Illegal move"):
        chess.apply_action(state, "white", "e2e5")  # Can't move pawn 3 squares


def test_apply_action_invalid_format(chess):
    state = chess.initial_state()
    with pytest.raises(InvalidActionError, match="Invalid move format"):
        chess.apply_action(state, "white", "invalid")


def test_apply_action_game_over(chess):
    # Create a state where the game is over
    state = chess.initial_state()
    state["result"] = "white_wins"

    with pytest.raises(InvalidActionError, match="Game is already over"):
        chess.apply_action(state, "white", "e2e4")


def test_apply_action_does_not_mutate_input(chess):
    state = chess.initial_state()
    original_fen = state["fen"]
    original_moves = list(state["moves"])

    new_state = chess.apply_action(state, "white", "e2e4")

    assert state["fen"] == original_fen
    assert state["moves"] == original_moves
    assert new_state["fen"] != state["fen"]


def test_turn_alternates(chess):
    state = chess.initial_state()

    # White moves
    state = chess.apply_action(state, "white", "e2e4")
    assert chess.legal_actions(state, "white") == []
    assert len(chess.legal_actions(state, "black")) > 0

    # Black moves
    state = chess.apply_action(state, "black", "e7e5")
    assert len(chess.legal_actions(state, "white")) > 0
    assert chess.legal_actions(state, "black") == []


def test_not_terminal_during_play(chess):
    state = chess.initial_state()
    assert chess.is_terminal(state) is False

    state = chess.apply_action(state, "white", "e2e4")
    assert chess.is_terminal(state) is False


def test_terminal_after_result(chess):
    state = chess.initial_state()
    state["result"] = "white_wins"
    assert chess.is_terminal(state) is True

    state["result"] = "black_wins"
    assert chess.is_terminal(state) is True

    state["result"] = "draw"
    assert chess.is_terminal(state) is True


def test_no_actions_after_game_over(chess):
    state = chess.initial_state()
    state["result"] = "white_wins"

    assert chess.legal_actions(state, "white") == []
    assert chess.legal_actions(state, "black") == []


def test_view_state_returns_full_state(chess):
    """Chess has no hidden information."""
    state = chess.initial_state()
    state = chess.apply_action(state, "white", "e2e4")

    white_view = chess.view_state(state, "white")
    black_view = chess.view_state(state, "black")

    # Both see the same thing
    assert white_view["fen"] == black_view["fen"]
    assert white_view["moves"] == black_view["moves"]


def test_scholars_mate(chess):
    """Test checkmate detection with scholar's mate."""
    state = chess.initial_state()

    # 1. e4 e5
    state = chess.apply_action(state, "white", "e2e4")
    state = chess.apply_action(state, "black", "e7e5")

    # 2. Bc4 Nc6
    state = chess.apply_action(state, "white", "f1c4")
    state = chess.apply_action(state, "black", "b8c6")

    # 3. Qh5 Nf6??
    state = chess.apply_action(state, "white", "d1h5")
    state = chess.apply_action(state, "black", "g8f6")

    # 4. Qxf7# checkmate
    state = chess.apply_action(state, "white", "h5f7")

    assert state["result"] == "white_wins"
    assert chess.is_terminal(state) is True


def test_fools_mate(chess):
    """Test fastest possible checkmate."""
    state = chess.initial_state()

    # 1. f3 e5
    state = chess.apply_action(state, "white", "f2f3")
    state = chess.apply_action(state, "black", "e7e5")

    # 2. g4 Qh4# checkmate
    state = chess.apply_action(state, "white", "g2g4")
    state = chess.apply_action(state, "black", "d8h4")

    assert state["result"] == "black_wins"
    assert chess.is_terminal(state) is True


def test_pawn_promotion(chess):
    """Test that pawn promotion works."""
    # Set up a position where white can promote
    state = {
        "fen": "8/P7/8/8/8/8/8/4K2k w - - 0 1",
        "moves": [],
        "result": None,
    }

    # Promote to queen
    actions = chess.legal_actions(state, "white")
    assert "a7a8q" in actions  # Promote to queen
    assert "a7a8r" in actions  # Promote to rook
    assert "a7a8b" in actions  # Promote to bishop
    assert "a7a8n" in actions  # Promote to knight

    new_state = chess.apply_action(state, "white", "a7a8q")
    assert "Q" in new_state["fen"]  # Queen appeared


def test_castling(chess):
    """Test that castling works."""
    # Position where white can castle kingside
    state = {
        "fen": "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
        "moves": [],
        "result": None,
    }

    actions = chess.legal_actions(state, "white")
    assert "e1g1" in actions  # Kingside castle
    assert "e1c1" in actions  # Queenside castle

    new_state = chess.apply_action(state, "white", "e1g1")
    # King should be on g1, rook on f1 -> R4RK1 in the last rank
    assert "R4RK1" in new_state["fen"]


def test_en_passant(chess):
    """Test that en passant works."""
    state = chess.initial_state()

    # Set up en passant position
    # 1. e4 a6 2. e5 d5
    state = chess.apply_action(state, "white", "e2e4")
    state = chess.apply_action(state, "black", "a7a6")
    state = chess.apply_action(state, "white", "e4e5")
    state = chess.apply_action(state, "black", "d7d5")

    # White can capture en passant
    actions = chess.legal_actions(state, "white")
    assert "e5d6" in actions  # En passant capture


def test_stalemate(chess):
    """Test stalemate detection."""
    # Black king a8, white king b6, white queen d8
    # After Qc7, black is stalemated (not in check, no legal moves)
    pre_stalemate = {
        "fen": "k2Q4/8/1K6/8/8/8/8/8 w - - 0 1",
        "moves": [],
        "result": None,
    }

    result_state = chess.apply_action(pre_stalemate, "white", "d8c7")
    assert result_state["result"] == "draw"
