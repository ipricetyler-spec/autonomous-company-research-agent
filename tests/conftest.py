from __future__ import annotations

from pathlib import Path

import pytest

from research_agent.database import Database


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    database.init()
    return database

