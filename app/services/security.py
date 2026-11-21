"""Password hashing (bcrypt) and JWT creation / decoding."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app import config


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id in the token. Raises jwt.PyJWTError if invalid or expired."""
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    return int(payload["sub"])
