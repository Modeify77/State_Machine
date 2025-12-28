from abc import ABC, abstractmethod


class StateMachine(ABC):
    """Base interface for all game templates."""

    @property
    @abstractmethod
    def template_id(self) -> str:
        """Unique identifier, e.g., 'chess.v1'"""
        pass

    @property
    @abstractmethod
    def roles(self) -> list[str]:
        """Required roles, e.g., ['white', 'black']"""
        pass

    @abstractmethod
    def initial_state(self) -> dict:
        """Return the starting state."""
        pass

    @abstractmethod
    def legal_actions(self, state: dict, role: str) -> list[str]:
        """Return list of legal actions for this role in this state."""
        pass

    @abstractmethod
    def apply_action(self, state: dict, role: str, action: str) -> dict:
        """Apply action and return new state. Raises if illegal."""
        pass

    @abstractmethod
    def is_terminal(self, state: dict) -> bool:
        """Return True if no more actions are possible."""
        pass

    @abstractmethod
    def view_state(self, state: dict, role: str) -> dict:
        """Return state as visible to this role (for hidden information games)."""
        pass
