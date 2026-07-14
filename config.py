import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file in development and local environments.
# Render and other production platforms already use actual environment variables.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def _int_env(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = _int_env("DB_PORT", 3306)
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "")
SECRET_KEY = os.getenv("SECRET_KEY", "naturviagens-secret-key")
