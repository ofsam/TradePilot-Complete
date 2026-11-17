import dis
import marshal
from pathlib import Path

pyc = Path(__file__).resolve().parents[1] / "app" / "__pycache__" / "main.cpython-311.pyc"
code = marshal.loads(pyc.read_bytes()[16:])
print("co_names:", code.co_names)
print("co_filename:", code.co_filename)
print("--- first 80 instructions ---")
dis.dis(code)
