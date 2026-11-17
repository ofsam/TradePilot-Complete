"""Inventory surviving .pyc modules for TradePilot restore."""
from __future__ import annotations

import marshal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def inventory(pyc: Path) -> str:
    code = marshal.loads(pyc.read_bytes()[16:])
    lines: list[str] = []

    def walk(c, indent: int = 0) -> None:
        pad = "  " * indent
        args = ", ".join(c.co_varnames[: c.co_argcount])
        lines.append(f"{pad}def {c.co_name}({args}):")
        consts = [
            repr(x)
            for x in c.co_consts
            if isinstance(x, (str, int, float, bool)) or x is None
        ]
        if consts:
            lines.append(f"{pad}  # consts: {', '.join(consts[:40])}")
        lines.append(f"{pad}  # names: {', '.join(c.co_names)}")
        for x in c.co_consts:
            if hasattr(x, "co_code"):
                walk(x, indent + 1)

    walk(code)
    return "\n".join(lines)


def grab_consts(pyc: Path) -> list:
    code = marshal.loads(pyc.read_bytes()[16:])
    vals: list = []

    def walk(c) -> None:
        for x in c.co_consts:
            if isinstance(x, (int, float)) and x in {3.5, 5.0, 5, 2.0, 100, 15, 10, 7}:
                vals.append(x)
            if isinstance(x, str) and any(
                k in x.lower()
                for k in ("break", "protect", "target_r", "h4h1", "otp", "brevo")
            ):
                vals.append(x[:120])
            if hasattr(x, "co_code"):
                walk(x)

    walk(code)
    return vals


RELS = [
    "app/__pycache__/auth.cpython-311.pyc",
    "app/__pycache__/desk.cpython-311.pyc",
    "app/__pycache__/notify.cpython-311.pyc",
    "app/__pycache__/main.cpython-311.pyc",
    "app/__pycache__/config.cpython-311.pyc",
    "app/__pycache__/models.cpython-311.pyc",
    "app/__pycache__/db.cpython-311.pyc",
    "app/strategy/__pycache__/defaults.cpython-311.pyc",
    "app/strategy/__pycache__/store.cpython-311.pyc",
    "app/strategy/__pycache__/engine.cpython-311.pyc",
    "app/routers/__pycache__/strategy.cpython-311.pyc",
    "app/mt5/__pycache__/adapter.cpython-311.pyc",
    "app/mt5/__pycache__/execution.cpython-311.pyc",
]


def main() -> None:
    for rel in RELS:
        p = ROOT / rel
        if not p.exists():
            print("missing", rel)
            continue
        name = rel.replace("__pycache__/", "").replace(".cpython-311.pyc", ".inv.txt").replace("/", "_")
        text = inventory(p)
        (OUT / name).write_text(text, encoding="utf-8")
        print("wrote", name, "lines", len(text.splitlines()), "notable", grab_consts(p)[:20])


if __name__ == "__main__":
    main()
