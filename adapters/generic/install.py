import argparse
import shutil
from pathlib import Path


def install(destination: Path) -> Path:
    root = Path(__file__).resolve().parents[2]
    target = destination.expanduser().resolve() / "sharewell"
    if target.exists():
        raise FileExistsError("SKILL_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "skills" / "sharewell", target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    runtime = target / "runtime"
    runtime.mkdir()
    for name in ("core", "scripts", "providers"):
        shutil.copytree(root / name, runtime / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(install(args.skills_dir))
    except (OSError, shutil.Error):
        parser.exit(1, "INSTALL_FAILED\n")
