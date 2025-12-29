import copy

import chess

from engine.errors import InvalidActionError
from engine.templates.base import StateMachine


class Chess(StateMachine):
    """Chess game template using python-chess for rules."""

    @property
    def template_id(self) -> str:
        return "chess.v1"

    @property
    def roles(self) -> list[str]:
        return ["white", "black"]

    def initial_state(self) -> dict:
        board = chess.Board()
        return {
            "fen": board.fen(),
            "moves": [],  # Move history in UCI notation
            "result": None,  # None, "white_wins", "black_wins", "draw"
        }

    def _board_from_state(self, state: dict) -> chess.Board:
        """Reconstruct board from FEN."""
        return chess.Board(state["fen"])

    def _current_role(self, state: dict) -> str:
        """Determine whose turn it is from FEN."""
        board = self._board_from_state(state)
        return "white" if board.turn == chess.WHITE else "black"

    def legal_actions(self, state: dict, role: str) -> list[str]:
        # No actions if game is over
        if state["result"] is not None:
            return []

        # No actions if it's not your turn
        if self._current_role(state) != role:
            return []

        board = self._board_from_state(state)
        return [move.uci() for move in board.legal_moves]

    def apply_action(self, state: dict, role: str, action: str) -> dict:
        # Check if game is over
        if state["result"] is not None:
            raise InvalidActionError("Game is already over")

        # Check if it's this player's turn
        if self._current_role(state) != role:
            raise InvalidActionError("Not your turn")

        board = self._board_from_state(state)

        # Parse and validate move
        try:
            move = chess.Move.from_uci(action)
        except ValueError:
            raise InvalidActionError(f"Invalid move format: {action}")

        if move not in board.legal_moves:
            raise InvalidActionError(f"Illegal move: {action}")

        # Apply move
        board.push(move)

        new_state = copy.deepcopy(state)
        new_state["fen"] = board.fen()
        new_state["moves"].append(action)

        # Check for game end
        if board.is_checkmate():
            # Current turn lost (they're in checkmate)
            winner = "black" if board.turn == chess.WHITE else "white"
            new_state["result"] = f"{winner}_wins"
        elif board.is_stalemate():
            new_state["result"] = "draw"
        elif board.is_insufficient_material():
            new_state["result"] = "draw"
        elif board.is_fifty_moves():
            new_state["result"] = "draw"
        elif board.is_repetition():
            new_state["result"] = "draw"

        return new_state

    def is_terminal(self, state: dict) -> bool:
        return state["result"] is not None

    def view_state(self, state: dict, role: str) -> dict:
        # Chess has no hidden information
        return copy.deepcopy(state)
