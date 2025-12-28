import engine.db as db_module


async def get_agent_by_token(token: str) -> dict | None:
    """Look up an agent by their authentication token.

    Args:
        token: The bearer token to look up

    Returns:
        Agent dict if found, None otherwise
    """
    return await db_module.get_agent_by_token(token, db_path=db_module.DATABASE_PATH)
