import dis
import marshal
from pathlib import Path

pyc = Path(__file__).resolve().parents[1] / "app" / "__pycache__" / "desk.cpython-311.pyc"
code = marshal.loads(pyc.read_bytes()[16:])
for const in code.co_consts:
    if hasattr(const, "co_code") and const.co_name in {"run_cycle", "_loop", "_execute"}:
        print("====", const.co_name, "====")
        dis.dis(const)
        print()
