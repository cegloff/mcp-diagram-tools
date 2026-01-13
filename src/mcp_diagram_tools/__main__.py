#!/usr/bin/env python3
"""
MCP Diagram Tools - Entry Point

Supports multiple transport modes:
- stdio: Standard I/O (default, for Claude Desktop)
- sse: Server-Sent Events over HTTP
- http: Streamable HTTP transport
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="MCP server for diagram operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with STDIO transport (default, for Claude Desktop)
  mcp-diagram-tools

  # Run with SSE transport on port 8080
  mcp-diagram-tools --transport sse --port 8080

  # Run with HTTP transport on custom port
  mcp-diagram-tools --transport http --port 3000

  # Specify project directory for file operations
  mcp-diagram-tools --project-dir /path/to/files

Note: Mermaid conversion requires Node.js with @excalidraw/mermaid-to-excalidraw installed.
"""
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default="stdio",
        help="Transport mode (default: stdio)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for SSE/HTTP transport (default: 8080)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind for SSE/HTTP transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        default=os.getcwd(),
        help="Project directory for file operations (default: current directory)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__import__('mcp_diagram_tools').__version__}"
    )

    args = parser.parse_args()

    # Set project directory environment variable
    os.environ["MCP_PROJECT_DIR"] = os.path.abspath(args.project_dir)

    # Import server after setting environment
    from .server import mcp

    if args.transport == "stdio":
        # Standard STDIO transport (default)
        mcp.run()

    elif args.transport == "sse":
        # SSE transport
        try:
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Route
            import uvicorn

            sse = SseServerTransport("/messages/")

            async def handle_sse(request):
                async with sse.connect_sse(
                    request.scope, request.receive, request._send
                ) as streams:
                    await mcp._mcp_server.run(
                        streams[0], streams[1], mcp._mcp_server.create_initialization_options()
                    )

            app = Starlette(
                routes=[
                    Route("/sse", endpoint=handle_sse),
                    Route("/messages/", endpoint=sse.handle_post_message, methods=["POST"]),
                ],
            )

            print(f"Starting SSE server on {args.host}:{args.port}")
            print(f"SSE endpoint: http://{args.host}:{args.port}/sse")
            print(f"Project directory: {args.project_dir}")
            uvicorn.run(app, host=args.host, port=args.port)

        except ImportError as e:
            print(f"Error: SSE transport requires additional dependencies: {e}")
            print("Install with: pip install 'mcp-diagram-tools[sse]'")
            sys.exit(1)

    elif args.transport == "http":
        # Streamable HTTP transport
        try:
            from mcp.server.streamable_http import StreamableHTTPServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Route
            import uvicorn

            transport = StreamableHTTPServerTransport(
                mcp_endpoint="/mcp",
                messages_endpoint="/messages",
            )

            async def handle_mcp(request):
                return await transport.handle_request(
                    request.scope, request.receive, request._send, mcp._mcp_server
                )

            app = Starlette(
                routes=[
                    Route("/mcp", endpoint=handle_mcp, methods=["GET", "POST"]),
                    Route("/messages", endpoint=handle_mcp, methods=["POST"]),
                ],
            )

            print(f"Starting HTTP server on {args.host}:{args.port}")
            print(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
            print(f"Project directory: {args.project_dir}")
            uvicorn.run(app, host=args.host, port=args.port)

        except ImportError as e:
            print(f"Error: HTTP transport requires additional dependencies: {e}")
            print("Install with: pip install 'mcp-diagram-tools[http]'")
            sys.exit(1)


if __name__ == "__main__":
    main()
