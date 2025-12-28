from fastapi import Request

from engine.auth import get_agent_by_token
from engine.errors import UnauthorizedError


async def get_current_agent(request: Request) -> dict:
    """Extract and validate the bearer token from the request.

    Args:
        request: The incoming FastAPI request

    Returns:
        The authenticated agent dict

    Raises:
        UnauthorizedError: If token is missing or invalid
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise UnauthorizedError("Missing authorization header")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Invalid authorization header format")

    token = parts[1]
    agent = await get_agent_by_token(token)

    if not agent:
        raise UnauthorizedError("Invalid token")

    return agent
