# Claude Code adapter

The root `.claude-plugin/plugin.json` discovers the same canonical skill. The
root `.mcp.json` supplies the official Binance Agent OS MCP endpoint when the
plugin is enabled; Claude Code asks for its normal server approval and OAuth.
For a local development load, start Claude Code with its documented plugin flag:

```text
claude --plugin-dir <absolute-path-to-sharewell>
```

Invoke `/sharewell:sharewell` or ask to use Sharewell. Configure the official
Binance MCP separately through the host; Binance documents:

```text
claude mcp add binance-mcp-server --transport http https://agent.binance.com/mcp/agentic
```

Use `/mcp` to finish authentication. Reuse an existing connection. A Claude
environment without local Python execution cannot run this package's core.
Claude Code is not installed in the build environment, so native loading and
authenticated tool invocation have not yet been verified here. A Claude
marketplace entry is intentionally not added; the GitHub repository and
`--plugin-dir` path are the smallest supported distribution path for this commit.
