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
    """
    Must set DATA_KEY too, not just SECRET_KEY -- this test originally didn't,
    and passed locally anyway only because the developer's own .env happened
    to have JOINTX_DATA_KEY set, populating Config.DATA_KEY at import time
    before this test ever ran. CI has no .env file, so Config.DATA_KEY was
    genuinely empty there and correctly caught this test's gap: it never
    actually exercised the "real secret key AND real data key" case it
    claimed to.
    """
    original_demo = Config.DEMO_MODE
    original_key = Config.SECRET_KEY
    original_data_key = Config.DATA_KEY
    try:
        Config.DEMO_MODE = False
        Config.SECRET_KEY = "a-real-random-secret-key-value"
        Config.DATA_KEY = "gCzvSShIS37Ssimc-wGhrKDOUDYPMNMagufv6YlmzLo="
        Config.validate_for_production()  # must not raise
    finally:
        Config.DEMO_MODE = original_demo
        Config.SECRET_KEY = original_key
        Config.DATA_KEY = original_data_key
