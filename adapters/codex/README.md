# Codex adapter

The root `.codex-plugin/plugin.json` and `skills/sharewell/` form the plugin.
For a local skill installation without a marketplace, run from the plugin root:

```text
python -B adapters/generic/install.py --skills-dir <your-project>/.codex/skills
```

Use the selected project's actual absolute path. Restart/reload the host's skill
discovery, then ask it to use Sharewell. The installer does not edit global state.

Connect the official Binance MCP using the host's OAuth flow. Binance documents:

```text
codex mcp add binance-mcp-server --url https://agent.binance.com/mcp/agentic --oauth-client-id codex
```

Reuse an existing connection rather than adding a duplicate. The user's host
version must accept this command; inspect `codex mcp add --help` first. No API
key or client secret belongs in Sharewell. A project skill install and a Codex
marketplace install are different delivery paths; no marketplace is configured
by this package's installer.
