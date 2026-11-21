"""Application settings, read from environment variables."""
import os
import warnings

DEFAULT_SECRET = "dev-only-secret-change-me"

SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_SECRET)
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./expense_tracker.db")

if SECRET_KEY == DEFAULT_SECRET:
    warnings.warn(
        "SECRET_KEY is not set; using an insecure development default. "
        "Set the SECRET_KEY environment variable before deploying.",
        stacklevel=1,
    )
