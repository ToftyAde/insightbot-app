import os

# Read from environment with sensible defaults
DATA_ROOT = os.getenv("DATA_ROOT", "./data")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", os.path.join(DATA_ROOT, "processed", "latest"))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "English")
PORT = int(os.getenv("PORT", "5001"))
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
