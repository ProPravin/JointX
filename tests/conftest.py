import os
import tempfile

import pytest


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["JOINTX_DB_PATH"] = db_path
    os.environ["JOINTX_DEMO_MODE"] = "true"

    # config.settings.Config is a class attribute frozen at first import time
    # (e.g. by ml/model_loader.py, which several tests import transitively
    # during collection, well before this fixture runs). Setting the env var
    # above is not enough on its own once that first import has already
    # happened — patch the class attribute directly so every test really
    # does run against its own throwaway DB, never the real data/jointx.db.
    from config.settings import Config

    original_db_path = Config.DATABASE_PATH
    original_demo_mode = Config.DEMO_MODE
    Config.DATABASE_PATH = db_path
    Config.DEMO_MODE = True

    from app import create_app

    application = create_app()
    application.config.update(TESTING=True)

    yield application

    from database.database import close_connection

    close_connection()  # release the SQLite file handle before deleting it (required on Windows)
    Config.DATABASE_PATH = original_db_path
    Config.DEMO_MODE = original_demo_mode
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
