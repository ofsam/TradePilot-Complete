import dis
import marshal
from pathlib import Path

pyc = Path(__file__).resolve().parents[1] / "_recover" / "pyc_backup" / "app_routers___pycache___strategy.cpython-311.pyc"
code = marshal.loads(pyc.read_bytes()[16:])
for const in code.co_consts:
    if hasattr(const, "co_code") and const.co_name in {"scan", "execute", "_saved_limits", "sent_today"}:
        print("====", const.co_name, "====")
        print("names:", const.co_names)
        # print string/float consts related to kwargs
        print("consts:", [c for c in const.co_consts if isinstance(c, (str, int, float, tuple))])
        dis.dis(const)
        print()
