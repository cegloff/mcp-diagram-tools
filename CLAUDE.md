# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run the server (STDIO mode - default)
mcp-diagram-tools
# or
python -m mcp_diagram_tools

# Run with SSE transport
mcp-diagram-tools --transport sse --port 8080

# Run with HTTP transport
mcp-diagram-tools --transport http --port 8080

# Optional dependencies for full functionality
playwright install chromium                         # For diagram rendering
npm install -g @excalidraw/mermaid-to-excalidraw   # For Mermaid conversion
npm install -g excalidraw-brute-export-cli         # For Excalidraw verification
```

## Architecture

This is an MCP (Model Context Protocol) server that provides diagram manipulation tools. The server exposes tools for reading, writing, rendering, and converting diagrams across multiple formats.

### Project Structure

- `src/mcp_diagram_tools/server.py` - Core implementation with all MCP tools and format parsers
- `src/mcp_diagram_tools/__main__.py` - CLI entry point with transport mode handling (stdio/sse/http)

### Key Components in server.py

**Format Parsers** (reading):
- `_read_drawio()` - Parses draw.io XML, handles both mxfile and mxGraphModel formats
- `_read_excalidraw()` - Parses Excalidraw JSON, extracts nodes/edges/text
- `_read_svg()` - Parses SVG, counts shapes and extracts text

**Format Writers** (creating diagrams):
- `_create_drawio_xml()` - Generates draw.io mxfile XML structure
- `_create_excalidraw_json()` - Generates Excalidraw JSON with proper element bindings
- `_create_svg()` - Generates SVG with shapes and arrows

**MCP Tools** (exposed to clients):
- `diagram_read` - Parse diagram files to extract structure
- `diagram_write` - Create diagrams from nodes/edges definitions
- `diagram_render` - Export to PNG/SVG using Playwright or cairosvg
- `diagram_convert` - Convert between diagram formats
- `diagram_from_mermaid` - Convert Mermaid syntax to Excalidraw (requires Node.js)
- `excalidraw_verify` - Validate Excalidraw files with real app rendering

### Path Security

All file operations use `_resolve_path()` which enforces that paths stay within `PROJECT_DIR` (configurable via `--project-dir` or `MCP_PROJECT_DIR` env var).

### Transport Modes

The server supports three transport modes configured in `__main__.py`:
- **stdio** (default): Standard I/O for Claude Desktop integration
- **sse**: Server-Sent Events using Starlette + uvicorn
- **http**: Streamable HTTP using `StreamableHTTPSessionManager`
