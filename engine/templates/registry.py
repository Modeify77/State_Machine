from engine.errors import NotFoundError
from engine.templates.base import StateMachine

_templates: dict[str, StateMachine] = {}


def register_template(template: StateMachine) -> None:
    """Register a template in the registry."""
    _templates[template.template_id] = template


def get_template(template_id: str) -> StateMachine:
    """Look up a template by ID.

    Args:
        template_id: The template identifier (e.g., 'chess.v1')

    Returns:
        The StateMachine instance

    Raises:
        NotFoundError: If template_id is not registered
    """
    if template_id not in _templates:
        raise NotFoundError(f"Template '{template_id}' not found")
    return _templates[template_id]


def list_templates() -> list[str]:
    """Return list of registered template IDs."""
    return list(_templates.keys())


# Register built-in templates
from engine.templates.rps import RockPaperScissors
from engine.templates.chess import Chess

register_template(RockPaperScissors())
register_template(Chess())
