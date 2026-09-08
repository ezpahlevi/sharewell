import ast
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import tokenize
import unittest
import zipfile
from pathlib import Path

from core.schemas import now_ms
from fixtures import snapshot
from scripts.package_release import package

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_production_python_has_no_prose_comments_or_docstrings(self):
        paths = []
        for name in ("core", "providers", "scripts", "adapters/generic", "skills/sharewell/scripts"):
            paths.extend((ROOT / name).rglob("*.py"))
        issues = []
        for path in sorted(paths):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.COMMENT:
                    issues.append((str(path.relative_to(ROOT)), token.start[0], "COMMENT"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    issues.append((str(path.relative_to(ROOT)), node.lineno, "DOCSTRING"))
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) > 32:
                    value = node.value.strip()
                    allowed = value == "https://agent.binance.com/mcp/agentic" or value.upper().startswith(
                        ("CREATE ", "SELECT ", "INSERT ", "UPDATE ")
                    )
                    if not allowed:
                        issues.append((str(path.relative_to(ROOT)), node.lineno, "LONG_STRING"))
        self.assertEqual(issues, [])

    def test_zip_is_reproducible_and_has_verifiable_source_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            package(first)
            package(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertTrue(all(name.startswith("sharewell/") for name in names))
                self.assertFalse(any("__pycache__" in name or name.endswith(".sqlite") or "/.env" in name for name in names))
                self.assertIn("sharewell/.mcp.json", names)
                self.assertIn("sharewell/LICENSE", names)
                self.assertNotIn("sharewell/docs/RESUME.md", names)
                manifest = json.loads(archive.read("sharewell/release-manifest.json"))
                for name, expected in manifest["files"].items():
                    self.assertEqual(hashlib.sha256(archive.read("sharewell/" + name)).hexdigest(), expected)
            with self.assertRaises(FileExistsError):
                package(first)

    def test_zip_is_identical_for_lf_and_crlf_sources(self):
        files = {
            "README.md": "readme\n",
            ".gitignore": "state\n",
            ".mcp.json": "{}\n",
            "LICENSE": "MIT\n",
            ".codex-plugin/plugin.json": '{"name":"sharewell","version":"1"}\n',
            ".claude-plugin/plugin.json": "{}\n",
            "skills/sharewell/SKILL.md": "skill\n",
            "core/journal.py": "from pathlib import Path\n",
            "providers/binance_mcp.py": "VALUE = 1\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            roots = []
            for newline in ("\n", "\r\n"):
                root = Path(directory) / ("lf" if newline == "\n" else "crlf")
                for name, content in files.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content.replace("\n", newline).encode())
                roots.append(root)
            first = Path(directory) / "lf.zip"
            second = Path(directory) / "crlf.zip"
            package(first, roots[0])
            package(second, roots[1])
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_repository_marketplace_registers_root_plugin(self):
        marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(marketplace["name"], "sharewell")
        self.assertEqual(marketplace["interface"]["displayName"], "Sharewell")
        self.assertEqual(marketplace["plugins"], [{
            "name": "sharewell",
            "source": {"source": "local", "path": "./"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }])

    def test_host_manifests_reference_official_mcp_without_credentials(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["binance-agentic"]
        self.assertEqual(server, {"type": "http", "url": "https://agent.binance.com/mcp/agentic"})
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(codex["mcpServers"], "./.mcp.json")
        claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertNotIn("token", json.dumps(codex).lower())
        self.assertNotIn("token", json.dumps(claude).lower())

    def test_self_contained_install_runs_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="sharewell package ") as directory:
            skills = Path(directory) / ".cursor" / "skills"
            command = [sys.executable, "-B", str(ROOT / "adapters/generic/install.py"), "--skills-dir", str(skills)]
            installed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            target = skills / "sharewell"
            self.assertEqual((target / "SKILL.md").read_bytes(), (ROOT / "skills/sharewell/SKILL.md").read_bytes())
            data = snapshot()
            data["observed_at"] = now_ms()
            data["quotes"][0]["observed_at"] = data["observed_at"]
            request = Path(directory) / "request.json"
            request.write_text(json.dumps({"snapshot": data}), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(target / "scripts/run.py"), "analyze", "--input", str(request)],
                                    cwd=directory, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["result"]["total_value"], "200")
            again = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(again.returncode, 1)
            self.assertIn("INSTALL_FAILED", again.stderr)

    def test_full_plugin_launcher_resolves_without_cwd_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-B", str(ROOT / "skills/sharewell/scripts/run.py"), "--help"],
                                    cwd=directory, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("dispatch", result.stdout)


if __name__ == "__main__":
    unittest.main()
