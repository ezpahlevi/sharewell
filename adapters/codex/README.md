# Codex adapter

The root `.codex-plugin/plugin.json` and `skills/sharewell/` form the plugin.
For a local skill installation without a marketplace, run from the plugin root:

```text
python -B adapters/generic/install.py --skills-dir <your-project>/.codex/skills
```

Use the selected project's actual absolute path. Restart/reload the host's skill
discovery, then ask it to use Sharewell. The installer does not edit global state.

For the repository marketplace, use the current Codex CLI flow:

```text
codex plugin marketplace add ezpahlevi/sharewell
codex plugin add sharewell@sharewell
```

The repository's `.agents/plugins/marketplace.json` points at the plugin root;
the marketplace smoke test passes in an isolated Codex home.

The plugin manifest references the bundled `.mcp.json` endpoint. Connect the
official Binance MCP using the host's OAuth flow. Binance documents:

```text
codex mcp add binance-mcp-server --url https://agent.binance.com/mcp/agentic --oauth-client-id codex
```

Reuse an existing connection rather than adding a duplicate. The user's host
version must accept this command; inspect `codex mcp add --help` first. No API
key or client secret belongs in Sharewell. A project skill install and a Codex
marketplace install are different delivery paths. OAuth and Binance confirmation
remain interactive host steps.
