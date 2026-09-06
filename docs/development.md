# Development

Sharewell requires Python 3.11 or newer and has no runtime dependencies outside the standard library.

Run tests from the plugin root:

```powershell
python -B -m unittest discover -s tests -q
```

Validate the plugin and canonical skill with the bundled OpenAI validators. The validators require PyYAML in their own validation environment; PyYAML is not a Sharewell runtime dependency.

Production Python files live under `core`, `providers`, `scripts`, `adapters/generic`, and `skills/sharewell/scripts`. They contain no comments or docstrings. Runtime failures use the stable codes in [errors.md](errors.md). Long literals are limited to the official endpoint and SQL statements required by the journal.

Tests use synthetic fixtures and temporary SQLite files. Never add captured balances, account identifiers, OAuth material, private journals, or fabricated receipts to the repository.

Build the release archive only after all tests and validators pass:

```powershell
python -B scripts/package_release.py --output <new-zip-path>
```

Packaging is deterministic, refuses overwrite, excludes development handoff files and runtime state, and writes a SHA-256 manifest inside the archive.

The repository marketplace smoke test uses an isolated Codex home:

```powershell
codex plugin marketplace add <repository> --json
codex plugin add sharewell@sharewell --json
```

The marketplace metadata lives at `.agents/plugins/marketplace.json` and points
to the plugin root with `./`. GitHub Actions repeats the tests, compiles
production Python, and creates a temporary package without secrets or network
calls to Binance.
