"""Load a backed-up .pyc when the .py was wiped. Never reads __pycache__."""
from __future__ import annotations

import marshal
import sys
from pathlib import Path

# Keep imports from overwriting surviving bytecode while bootloaders exist.
sys.dont_write_bytecode = True

_BACKUP = Path(__file__).resolve().parents[1] / "_recover" / "pyc_backup"


def load_into(globals_dict: dict, backup_name: str) -> None:
    pyc = _BACKUP / backup_name
    if not pyc.is_file():
        raise FileNotFoundError(f"Missing bytecode backup: {pyc}")
    code = marshal.loads(pyc.read_bytes()[16:])
    exec(code, globals_dict)
