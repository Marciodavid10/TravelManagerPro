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

DB_HOST = "projetos.epcjc.net"
DB_PORT = 3306
DB_USER = "i253669"
DB_PASSWORD = "69oD#We$"
DB_NAME = "i253669_travelmanagerpro"
SECRET_KEY = os.getenv("SECRET_KEY", "naturviagens-secret-key")