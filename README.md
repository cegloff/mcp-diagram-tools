# MCP Diagram Tools

MCP server for diagram operations - read, write, render, and convert diagrams.

## Features

- **Read diagrams**: Parse `.drawio`, `.excalidraw`, `.svg` files to extract structure (nodes, edges, text)
- **Write diagrams**: Create diagrams from structured data (nodes and edges)
- **Render diagrams**: Export to PNG/SVG using headless browser rendering
- **Convert formats**: Convert between draw.io, Excalidraw, and SVG formats
- **Mermaid support**: Convert Mermaid syntax to Excalidraw diagrams (requires Node.js)
- **Verify Excalidraw**: Validate `.excalidraw` files using the real Excalidraw app

## Supported Formats

| Format | Read | Write | Render |
|--------|------|-------|--------|
| draw.io (.drawio, .xml) | Yes | Yes | PNG/SVG |
| Excalidraw (.excalidraw) | Yes | Yes | PNG/SVG |
| SVG (.svg) | Yes | Yes | PNG |
| PNG (.png) | - | - | Output only |

## Installation

```bash
pip install mcp-diagram-tools
```

### Additional Requirements

**For rendering (optional)**:
```bash
# Install Playwright browsers
playwright install chromium
```

**For Mermaid conversion (optional)**:
```bash
# Requires Node.js
npm install -g @excalidraw/mermaid-to-excalidraw
```

**For Excalidraw verification (optional)**:
```bash
npm install -g excalidraw-brute-export-cli
```

## Usage

### Transport Modes

The server supports three transport modes:

#### STDIO (Default)
For use with Claude Desktop and other MCP clients:
```bash
mcp-diagram-tools
# or
python -m mcp_diagram_tools
```

#### SSE (Server-Sent Events)
```bash
mcp-diagram-tools --transport sse --port 8080
```

#### HTTP (Streamable HTTP)
```bash
mcp-diagram-tools --transport http --port 8080
```

### Options

```
--transport     Transport mode: stdio, sse, http (default: stdio)
--port          Port for SSE/HTTP transport (default: 8080)
--host          Host to bind for SSE/HTTP transport (default: 0.0.0.0)
--project-dir   Project directory for file operations (default: current directory)
```

## Tools

### diagram_read
Read and parse a diagram file to extract its structure.

```json
{
  "path": "diagram.excalidraw"
}
```

Returns nodes, edges, text content, and metadata.

### diagram_write
Create a new diagram from node and edge definitions.

```json
{
  "path": "output.excalidraw",
  "nodes": "[{\"id\": \"1\", \"label\": \"Start\", \"type\": \"rectangle\", \"x\": 100, \"y\": 100}]",
  "edges": "[{\"source\": \"1\", \"target\": \"2\", \"label\": \"Next\"}]"
}
```

### diagram_render
Render a diagram to PNG or SVG.

```json
{
  "path": "diagram.excalidraw",
  "output_path": "output.png",
  "width": 1200,
  "height": 800
}
```

### diagram_convert
Convert between diagram formats.

```json
{
  "source_path": "diagram.drawio",
  "target_path": "diagram.excalidraw"
}
```

### diagram_from_mermaid
Create an Excalidraw diagram from Mermaid syntax.

```json
{
  "path": "flowchart.excalidraw",
  "mermaid_code": "flowchart LR\n    A[Start] --> B{Decision}\n    B -->|Yes| C[Process]\n    B -->|No| D[End]"
}
```

### excalidraw_verify
Verify an Excalidraw file renders correctly.

```json
{
  "path": "diagram.excalidraw"
}
```

## Claude Desktop Configuration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "diagram-tools": {
      "command": "mcp-diagram-tools",
      "args": ["--project-dir", "/path/to/your/project"]
    }
  }
}
```

## Development

```bash
# Clone the repository
git clone https://github.com/cegloff/mcp-diagram-tools.git
cd mcp-diagram-tools

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT License - see [LICENSE](LICENSE) for details.
