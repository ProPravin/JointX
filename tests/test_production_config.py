import pytest

from config.settings import Config, INSECURE_DEFAULT_SECRET_KEY


def test_validate_for_production_noop_in_demo_mode():
    original_demo, original_key = Config.DEMO_MODE, Config.SECRET_KEY
    try:
        Config.DEMO_MODE = True
        Config.SECRET_KEY = INSECURE_DEFAULT_SECRET_KEY
        Config.validate_for_production()  # must not raise
    finally:
        Config.DEMO_MODE, Config.SECRET_KEY = original_demo, original_key


def test_validate_for_production_rejects_default_secret_key():
    original_demo, original_key = Config.DEMO_MODE, Config.SECRET_KEY
    try:
        Config.DEMO_MODE = False
        Config.SECRET_KEY = INSECURE_DEFAULT_SECRET_KEY
        with pytest.raises(RuntimeError, match="placeholder"):
            Config.validate_for_production()
    finally:
        Config.DEMO_MODE, Config.SECRET_KEY = original_demo, original_key


def test_validate_for_production_passes_with_real_secret_key():
    original_demo, original_key = Config.DEMO_MODE, Config.SECRET_KEY
    try:
        Config.DEMO_MODE = False
        Config.SECRET_KEY = "a-real-random-secret-key-value"
        Config.validate_for_production()  # must not raise
    finally:
        Config.DEMO_MODE, Config.SECRET_KEY = original_demo, original_key
