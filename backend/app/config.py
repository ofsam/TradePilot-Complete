from pathlib import Path

from dotenv import load_dotenv

from app._pyc_boot import load_into

# Pydantic Settings reads env vars; make sure backend/.env is present first.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
load_into(globals(), "app___pycache___config.cpython-311.pyc")
