"""
Logging setup. IMPORTANT: never log raw patient identifiers, questionnaire
answers, or biometric feature values -- only high-level operational events.
"""
import logging
import os

from config.settings import Config


def get_logger(name):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    os.makedirs(Config.LOG_DIR, exist_ok=True)
    log_path = os.path.join(Config.LOG_DIR, "jointx.log")

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
    return logger
