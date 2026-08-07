import os

# Point the app at an in-memory database BEFORE importing anything that reads
# settings, otherwise importing main would create a stray careeros.db file.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
