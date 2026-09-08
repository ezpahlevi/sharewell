import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {"core", "providers", "adapters", "scripts", "skills", "tests", "docs",
               ".codex-plugin", ".claude-plugin"}
ROOT_FILES = {"README.md", ".gitignore", ".mcp.json", "LICENSE", "LICENSE.md", "pyproject.toml"}
SUFFIXES = {".py", ".md", ".json", ".toml"}
EXCLUDED = {"__pycache__", ".git", "state", "node_modules", ".venv", "runtime"}


def _source_bytes(path: Path, relative: Path) -> bytes:
    data = path.read_bytes()
    if relative.as_posix() in ROOT_FILES or path.suffix in SUFFIXES:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def package(destination: Path, root: Path = ROOT) -> dict:
    root = root.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("ZIP_EXISTS")
    manifest = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    entries = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink() or not path.is_file():
            continue
        if any(part in EXCLUDED for part in relative.parts) or any(part.startswith(".env") for part in relative.parts):
            continue
        if relative.parts[0] not in DIRECTORIES and relative.as_posix() not in ROOT_FILES:
            continue
        if len(relative.parts) > 1 and path.suffix not in SUFFIXES:
            continue
        if relative.as_posix() in {"docs/RESUME.md", "docs/implementation-plan.md"}:
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError("PATH_ESCAPE")
        entries[relative.as_posix()] = _source_bytes(path, relative)
    required = {"README.md", ".mcp.json", "LICENSE", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
                "skills/sharewell/SKILL.md", "core/journal.py", "providers/binance_mcp.py"}
    if not required <= entries.keys():
        raise ValueError("MISSING_RELEASE_FILES")
    release = {"name": manifest["name"], "version": manifest["version"],
               "files": {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}}
    entries["release-manifest.json"] = (json.dumps(release, indent=2, sort_keys=True) + "\n").encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in sorted(entries.items()):
                entry = zipfile.ZipInfo("sharewell/" + name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_STORED
                entry.create_system = 3
                entry.external_attr = 0o644 << 16
                archive.writestr(entry, data)
    return {"path": str(destination), "file_count": len(entries),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.output)))
    except (OSError, ValueError, zipfile.BadZipFile):
        parser.exit(1, "PACKAGE_FAILED\n")
