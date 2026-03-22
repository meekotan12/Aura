"""Use: Provides small password helper functions.
Where to use: Use this when the backend needs simple reusable password-related helpers.
Role: Utility layer. It keeps small helper logic separate from main business code.
"""

import bcrypt
import secrets
import string

_PASSWORD_ALPHABET = string.ascii_letters + string.digits
_BCRYPT_ROUNDS = 12
_BCRYPT_MAX_PASSWORD_BYTES = 72


def generate_secure_password(min_length: int = 10, max_length: int = 16) -> str:
    if min_length < 10:
        raise ValueError("min_length must be at least 10")
    if max_length < min_length:
        raise ValueError("max_length must be greater than or equal to min_length")

    length = secrets.randbelow(max_length - min_length + 1) + min_length

    # Ensure password policy is always satisfied.
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    remaining = [secrets.choice(_PASSWORD_ALPHABET) for _ in range(length - len(required))]

    chars = required + remaining
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def ensure_bcrypt_password_supported(password: str) -> None:
    if len(password.encode("utf-8")) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            "Password must be 72 bytes or fewer for bcrypt compatibility."
        )


def hash_password_bcrypt(password: str) -> str:
    ensure_bcrypt_password_supported(password)
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_password_bcrypt(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError as exc:
        if "longer than 72 bytes" in str(exc):
            return False
        raise
