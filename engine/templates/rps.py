import copy

from engine.errors import AlreadyActedError, InvalidActionError
from engine.templates.base import StateMachine

VALID_CHOICES = {"rock", "paper", "scissors"}

# Winning combinations: key beats value
BEATS = {
    "rock": "scissors",
    "paper": "rock",
    "scissors": "paper",
}


class RockPaperScissors(StateMachine):
    """Rock-Paper-Scissors game template.

    Game continues until there is a winner (draws reset for another round).
    """

    @property
    def template_id(self) -> str:
        return "rps.v1"

    @property
    def roles(self) -> list[str]:
        return ["player_1", "player_2"]

    def initial_state(self) -> dict:
        return {
            "phase": "commit",
            "choices": {"player_1": None, "player_2": None},
            "result": None,
            "round": 1,
            "history": [],  # Track previous rounds
        }

    def legal_actions(self, state: dict, role: str) -> list[str]:
        # No actions after game is resolved with a winner
        if state["result"] in ("player_1_wins", "player_2_wins"):
            return []

        # No actions if already committed this round
        if state["choices"].get(role) is not None:
            return []

        return ["rock", "paper", "scissors"]

    def apply_action(self, state: dict, role: str, action: str) -> dict:
        # Check if game is over (has a winner)
        if state["result"] in ("player_1_wins", "player_2_wins"):
            raise InvalidActionError("Game is already over")

        # Check if already committed this round
        if state["choices"].get(role) is not None:
            raise AlreadyActedError("Already submitted choice this round")

        # Validate action is valid choice
        if action not in VALID_CHOICES:
            raise InvalidActionError(f"Invalid choice: {action}")

        new_state = copy.deepcopy(state)
        new_state["choices"][role] = action

        # Check if both players have committed
        p1_choice = new_state["choices"]["player_1"]
        p2_choice = new_state["choices"]["player_2"]

        if p1_choice is not None and p2_choice is not None:
            result = self._compute_result(p1_choice, p2_choice)

            if result == "draw":
                # Record this round in history and reset for next round
                new_state["history"].append({
                    "round": new_state["round"],
                    "choices": {"player_1": p1_choice, "player_2": p2_choice},
                    "result": "draw",
                })
                new_state["round"] += 1
                new_state["choices"] = {"player_1": None, "player_2": None}
                # Phase stays "commit", result stays None
            else:
                # We have a winner!
                new_state["phase"] = "reveal"
                new_state["result"] = result

        return new_state

    def _compute_result(self, p1_choice: str, p2_choice: str) -> str:
        """Compute the winner based on choices."""
        if p1_choice == p2_choice:
            return "draw"
        elif BEATS[p1_choice] == p2_choice:
            return "player_1_wins"
        else:
            return "player_2_wins"

    def is_terminal(self, state: dict) -> bool:
        # Only terminal when there's a winner (not on draw)
        return state["result"] in ("player_1_wins", "player_2_wins")

    def view_state(self, state: dict, role: str) -> dict:
        """Return state with opponent's choice hidden during commit phase."""
        view = copy.deepcopy(state)

        # During commit phase, hide opponent's current choice
        if state["phase"] == "commit":
            opponent = "player_2" if role == "player_1" else "player_1"
            if state["choices"][opponent] is not None:
                view["choices"][opponent] = "hidden"

        return view
