"""
MCP Diagram Tools
=================

MCP server for diagram operations (Excalidraw, draw.io, SVG, Mermaid).

Supports:
- Reading: .excalidraw, .drawio, .svg
- Writing: .excalidraw, .drawio, .svg
- Rendering: to PNG/SVG
- Mermaid conversion (requires Node.js)

Transport modes:
- STDIO (default): For Claude Desktop and other MCP clients
- SSE: Server-Sent Events over HTTP
- HTTP: Streamable HTTP transport
"""

__version__ = "0.1.0"

from .server import create_server, mcp

__all__ = ["create_server", "mcp", "__version__"]
