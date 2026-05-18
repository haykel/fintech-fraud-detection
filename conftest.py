"""
Pytest configuration file
Configure Python path to include the project root
"""
import asyncio
import sys
from pathlib import Path

import pytest

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop.

    SQLAlchemy's async engine and asyncpg connection pool are bound to the
    event loop they are first used on. With the default pytest-asyncio per-test
    loop, our module-level engine (`infrastructure/postgres/repositories.py`)
    ends up "attached to a different loop" on the second test. Sharing one loop
    across the session keeps the engine valid throughout.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
