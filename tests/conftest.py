import os

import pytest
from httpx import ASGITransport, AsyncClient

import engine.db as db_module
from engine.db import init_db


@pytest.fixture
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # Patch the default database path for all db operations
    original_path = db_module.DATABASE_PATH
    db_module.DATABASE_PATH = db_path

    yield db_path

    db_module.DATABASE_PATH = original_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
async def client(test_db):
    """Async test client with initialized test database."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
