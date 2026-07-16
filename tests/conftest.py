from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_file=PROJECT_ROOT / "data" / "datos.json",
        processed_dir=tmp_path / "processed",
        chunk_rows=2,
        workers=1,
        query_threads=2,
    )


@pytest.fixture
def client(settings: Settings):
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
