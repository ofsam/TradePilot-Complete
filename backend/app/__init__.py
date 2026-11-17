"""Ensure backend/.env is loaded no matter which folder started uvicorn."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
