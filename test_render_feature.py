#!/usr/bin/env python3
"""Test script for the render feature of diagram_write."""

import sys
sys.path.insert(0, 'src')

import asyncio
import json
from mcp_diagram_tools.server import diagram_write

async def test_render():
    """Test diagram_write with render=True."""

    # Simple test diagram
    nodes = [
        {"id": "a", "label": "Node A", "type": "rectangle", "x": 50, "y": 50, "width": 100, "height": 50},
        {"id": "b", "label": "Node B", "type": "rectangle", "x": 200, "y": 50, "width": 100, "height": 50},
    ]

    edges = [
        {"id": "e1", "source": "a", "target": "b", "label": ""},
    ]

    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)

    print("Testing diagram_write with render=False...")
    result = await diagram_write(
        path="test_output.excalidraw",
        nodes=nodes_json,
        edges=edges_json,
        name="Test Diagram",
        render=False
    )
    print(f"Result (render=False): {result}\n")

    print("Testing diagram_write with render=True...")
    result = await diagram_write(
        path="test_output_rendered.excalidraw",
        nodes=nodes_json,
        edges=edges_json,
        name="Test Diagram Rendered",
        render=True
    )

    result_dict = json.loads(result)

    if "image" in result_dict:
        print("SUCCESS: Image was rendered!")
        print(f"  - Image type: {result_dict['image']['type']}")
        print(f"  - Media type: {result_dict['image']['media_type']}")
        print(f"  - Base64 length: {len(result_dict['image']['data'])} chars")

        # Save the image to verify it visually
        import base64
        png_data = base64.b64decode(result_dict['image']['data'])
        with open("test_output_rendered.png", "wb") as f:
            f.write(png_data)
        print(f"  - Saved to: test_output_rendered.png")
    elif "render_error" in result_dict:
        print(f"RENDER ERROR: {result_dict['render_error']}")
    else:
        print("No image in result - render may have been skipped")

    print(f"\nFull result: {result[:500]}...")

if __name__ == "__main__":
    asyncio.run(test_render())
