"""
Spec: P1 data layer #3 -- refuses to start in production with a database
inside the application directory, or (POSIX only) a world/group-readable
database file.
"""
import os
import tempfile

import pytest

from config.settings import Config, BASE_DIR


def _valid_prod_config():
    """A real secret key + data key so only the DB-location check can fail."""
    return {
        "SECRET_KEY": "a-real-random-secret-key-value",
        "DATA_KEY": "gCzvSShIS37Ssimc-wGhrKDOUDYPMNMagufv6YlmzLo=",
    }


def test_refuses_to_start_with_db_inside_app_directory():
    original = {"DEMO_MODE": Config.DEMO_MODE, "DATABASE_PATH": Config.DATABASE_PATH,
                "SECRET_KEY": Config.SECRET_KEY, "DATA_KEY": Config.DATA_KEY}
    try:
        Config.DEMO_MODE = False
        Config.DATABASE_PATH = os.path.join(BASE_DIR, "data", "jointx.db")
        for k, v in _valid_prod_config().items():
            setattr(Config, k, v)

        with pytest.raises(RuntimeError, match="inside the application directory"):
            Config.validate_for_production()
    finally:
        for k, v in original.items():
            setattr(Config, k, v)


def test_allows_db_outside_app_directory():
    original = {"DEMO_MODE": Config.DEMO_MODE, "DATABASE_PATH": Config.DATABASE_PATH,
                "SECRET_KEY": Config.SECRET_KEY, "DATA_KEY": Config.DATA_KEY}
    try:
        Config.DEMO_MODE = False
        Config.DATABASE_PATH = os.path.join(tempfile.gettempdir(), "jointx-outside-repo.db")
        for k, v in _valid_prod_config().items():
            setattr(Config, k, v)

        Config.validate_for_production()  # must not raise
    finally:
        for k, v in original.items():
            setattr(Config, k, v)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permission model only")
def test_refuses_to_start_with_world_readable_db():
    original = {"DEMO_MODE": Config.DEMO_MODE, "DATABASE_PATH": Config.DATABASE_PATH,
                "SECRET_KEY": Config.SECRET_KEY, "DATA_KEY": Config.DATA_KEY}
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        os.chmod(db_path, 0o644)  # world-readable -- the unsafe case
        Config.DEMO_MODE = False
        Config.DATABASE_PATH = db_path
        for k, v in _valid_prod_config().items():
            setattr(Config, k, v)

        with pytest.raises(RuntimeError, match="readable by group/other"):
            Config.validate_for_production()
    finally:
        os.remove(db_path)
        for k, v in original.items():
            setattr(Config, k, v)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permission model only")
def test_allows_0600_db_file():
    original = {"DEMO_MODE": Config.DEMO_MODE, "DATABASE_PATH": Config.DATABASE_PATH,
                "SECRET_KEY": Config.SECRET_KEY, "DATA_KEY": Config.DATA_KEY}
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        os.chmod(db_path, 0o600)
        Config.DEMO_MODE = False
        Config.DATABASE_PATH = db_path
        for k, v in _valid_prod_config().items():
            setattr(Config, k, v)

        Config.validate_for_production()  # must not raise
    finally:
        os.remove(db_path)
        for k, v in original.items():
            setattr(Config, k, v)
