import os
import tempfile

import pytest


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["JOINTX_DB_PATH"] = db_path
    os.environ["JOINTX_DEMO_MODE"] = "true"

    from app import create_app

    application = create_app()
    application.config.update(TESTING=True)

    yield application

    os.remove(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "changeme123"},
    )
    return client
