import runpy
import sys
from pathlib import Path

skill = Path(__file__).resolve().parents[1]
bundled = skill / "runtime"
root = bundled if bundled.is_dir() else skill.parent.parent
entry = root / "scripts" / "sharewell.py"
if not entry.is_file():
    raise SystemExit("RUNTIME_MISSING")
sys.path.insert(0, str(root))
runpy.run_path(str(entry), run_name="__main__")
