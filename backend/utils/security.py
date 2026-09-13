"""
Security helpers: password hashing (werkzeug, no plaintext ever stored) and
simple session-token utilities. No secrets are hard-coded; SECRET_KEY comes
from environment via config.settings.Config.
"""
import functools
import secrets

from flask import session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from config.roles import tier_for_role


def hash_password(plain_password: str) -> str:
    return generate_password_hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, plain_password)


def new_csrf_token() -> str:
    return secrets.token_hex(16)


def validate_password_strength(password: str):
    """
    Raises ValidationError if the password doesn't meet minimum production
    complexity: at least 8 characters, containing at least one letter and
    one digit. Deliberately not tied to a specific character-class regex
    beyond that so it doesn't reject legitimate passphrases.
    """
    from backend.utils.validators import ValidationError

    if not password or len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain at least one letter and one digit")


def login_required(view_func):
    """Decorator for API routes that require an authenticated healthcare worker."""

    @functools.wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("worker_id"):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return view_func(*args, **kwargs)

    return wrapped


def require_role(*allowed_tiers):
    """
    Decorator restricting a route to the given role tiers ("worker",
    "reviewer", "admin"). Must be applied AFTER (i.e. listed below)
    @login_required so session["worker_id"] is already guaranteed to exist.
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped(*args, **kwargs):
            tier = tier_for_role(session.get("worker_role"))
            if tier not in allowed_tiers:
                return jsonify({"success": False, "error": "You do not have permission to perform this action"}), 403
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
