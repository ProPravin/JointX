"""
Re-exports the root Config so code under config/ and backend/ can do:
    from config.settings import Config
without duplicating settings in two places.
"""
import importlib.util
import os

_root_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")
_spec = importlib.util.spec_from_file_location("jointx_root_config", _root_config_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

Config = _module.Config
