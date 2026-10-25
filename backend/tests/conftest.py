from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from documind.config import Settings
from documind.main import create_app


def make_settings(data_dir: Path, **overrides: Any) -> Settings:
    # _env_file=None: tests must not pick up a developer's local .env file.
    return Settings(_env_file=None, data_dir=data_dir, **overrides)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path / "data")


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # The context manager runs the lifespan (directory creation and schema initialisation).
    with TestClient(app) as test_client:
        yield test_client
