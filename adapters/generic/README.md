# Cursor and other skill-capable hosts

For Cursor, run from the Sharewell root:

```text
python -B adapters/generic/install.py --skills-dir <your-project>/.cursor/skills
```

For another host, pass its documented skills directory. This copies one
self-contained `sharewell` skill including the independent runtime. It refuses
to overwrite an existing installation and never copies a journal or credentials.
After installation, reload skill discovery and connect the official remote MCP
endpoint through the host's MCP/OAuth interface. No connection is configured by
this installer.

Compatibility requires native remote MCP authorization and confirmation, local
Python 3.11+ execution, and file I/O. A generic chat client with none of these
capabilities is not supported. Cursor's native authenticated workflow has not
been verified in this build environment.
