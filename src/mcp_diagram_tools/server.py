#!/usr/bin/env python3
"""
MCP Diagram Tools - Server Implementation
==========================================

Provides tools to read, write, render, and convert diagrams.

Supported formats:
- draw.io (.drawio, .xml) - XML-based diagrams
- Excalidraw (.excalidraw) - JSON-based diagrams
- SVG (.svg) - Scalable Vector Graphics
- PNG (.png) - Rendered output

Tools:
- diagram_read: Parse diagram structure (nodes, edges, text)
- diagram_write: Create a new diagram from structure
- diagram_render: Render diagram to PNG/SVG for visual verification
- diagram_convert: Convert between diagram formats
- excalidraw_verify: Verify Excalidraw file validity
- diagram_from_mermaid: Convert Mermaid syntax to Excalidraw
"""

import base64
import json
import os
import random
import string
import time
import zlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("MCP_PROJECT_DIR", os.getcwd())).resolve()


def _resolve_path(path: str) -> Path:
    """Resolve path relative to project directory and validate it stays within."""
    resolved = (PROJECT_DIR / path).resolve()
    try:
        resolved.relative_to(PROJECT_DIR.resolve())
    except ValueError:
        raise ValueError(f"Path '{path}' escapes the project directory")
    return resolved


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize on startup, cleanup on shutdown."""
    # Ensure project directory exists
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    yield


# Initialize the MCP server
mcp = FastMCP("mcp-diagram-tools", lifespan=server_lifespan)


def create_server() -> FastMCP:
    """Create and return the MCP server instance."""
    return mcp


# ============================================================================
# draw.io Parsing Utilities
# ============================================================================

def _decode_drawio_data(data: str) -> str:
    """Decode draw.io compressed/encoded cell data."""
    try:
        # URL decode
        decoded = unquote(data)
        # Base64 decode
        decoded = base64.b64decode(decoded)
        # Inflate (decompress)
        decoded = zlib.decompress(decoded, -15)
        return decoded.decode('utf-8')
    except Exception:
        # Return as-is if not encoded
        return data


def _parse_drawio_mxgraphmodel(root: ET.Element) -> dict:
    """Parse mxGraphModel structure from draw.io XML."""
    nodes = []
    edges = []

    # Find all mxCell elements
    for cell in root.iter('mxCell'):
        cell_id = cell.get('id', '')
        value = cell.get('value', '')
        style = cell.get('style', '')

        # Skip root cells (id 0 and 1)
        if cell_id in ('0', '1'):
            continue

        # Check if it's an edge
        source = cell.get('source')
        target = cell.get('target')

        if source and target:
            edges.append({
                "id": cell_id,
                "source": source,
                "target": target,
                "label": value,
                "style": style
            })
        elif value or cell.get('vertex') == '1':
            # It's a node
            geometry = cell.find('mxGeometry')
            geo_data = {}
            if geometry is not None:
                geo_data = {
                    "x": float(geometry.get('x', 0)),
                    "y": float(geometry.get('y', 0)),
                    "width": float(geometry.get('width', 0)),
                    "height": float(geometry.get('height', 0))
                }

            nodes.append({
                "id": cell_id,
                "label": value,
                "style": style,
                "geometry": geo_data
            })

    return {"nodes": nodes, "edges": edges}


def _read_drawio(file_path: Path) -> dict:
    """Read and parse a draw.io diagram."""
    content = file_path.read_text(encoding='utf-8')

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return {"error": f"Invalid XML: {str(e)}"}

    # draw.io files can have different structures
    diagrams = []

    # Check for mxfile structure (newer format)
    if root.tag == 'mxfile':
        for diagram in root.findall('.//diagram'):
            name = diagram.get('name', 'Untitled')
            diagram_data = diagram.text

            if diagram_data:
                # Decode compressed diagram data
                try:
                    decoded = _decode_drawio_data(diagram_data.strip())
                    diagram_root = ET.fromstring(decoded)
                    parsed = _parse_drawio_mxgraphmodel(diagram_root)
                    parsed['name'] = name
                    diagrams.append(parsed)
                except Exception:
                    # Try parsing child elements directly
                    mxgraph = diagram.find('.//mxGraphModel')
                    if mxgraph is not None:
                        parsed = _parse_drawio_mxgraphmodel(mxgraph)
                        parsed['name'] = name
                        diagrams.append(parsed)
            else:
                # Data might be in child elements
                mxgraph = diagram.find('.//mxGraphModel')
                if mxgraph is not None:
                    parsed = _parse_drawio_mxgraphmodel(mxgraph)
                    parsed['name'] = name
                    diagrams.append(parsed)

    # Check for direct mxGraphModel (older format)
    elif root.tag == 'mxGraphModel':
        parsed = _parse_drawio_mxgraphmodel(root)
        parsed['name'] = 'Main'
        diagrams.append(parsed)

    # Collect all unique text content
    all_text = set()
    total_nodes = 0
    total_edges = 0

    for d in diagrams:
        total_nodes += len(d.get('nodes', []))
        total_edges += len(d.get('edges', []))
        for node in d.get('nodes', []):
            if node.get('label'):
                all_text.add(node['label'])
        for edge in d.get('edges', []):
            if edge.get('label'):
                all_text.add(edge['label'])

    return {
        "format": "drawio",
        "diagrams": diagrams,
        "text_content": list(all_text),
        "metadata": {
            "diagram_count": len(diagrams),
            "total_nodes": total_nodes,
            "total_edges": total_edges
        }
    }


# ============================================================================
# Excalidraw Parsing
# ============================================================================

def _read_excalidraw(file_path: Path) -> dict:
    """Read and parse an Excalidraw diagram."""
    content = file_path.read_text(encoding='utf-8')

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {str(e)}"}

    elements = data.get('elements', [])

    nodes = []
    edges = []
    text_content = []

    for elem in elements:
        elem_type = elem.get('type', '')
        elem_id = elem.get('id', '')

        if elem_type == 'arrow' or elem_type == 'line':
            # These can be edges
            binding_start = elem.get('startBinding', {})
            binding_end = elem.get('endBinding', {})

            edges.append({
                "id": elem_id,
                "type": elem_type,
                "source": binding_start.get('elementId') if binding_start else None,
                "target": binding_end.get('elementId') if binding_end else None,
                "points": elem.get('points', [])
            })
        elif elem_type == 'text':
            text = elem.get('text', '')
            if text:
                text_content.append(text)
                nodes.append({
                    "id": elem_id,
                    "type": elem_type,
                    "text": text,
                    "x": elem.get('x', 0),
                    "y": elem.get('y', 0),
                    "width": elem.get('width', 0),
                    "height": elem.get('height', 0)
                })
        else:
            # Shapes (rectangle, ellipse, diamond, etc.)
            nodes.append({
                "id": elem_id,
                "type": elem_type,
                "x": elem.get('x', 0),
                "y": elem.get('y', 0),
                "width": elem.get('width', 0),
                "height": elem.get('height', 0),
                "backgroundColor": elem.get('backgroundColor'),
                "strokeColor": elem.get('strokeColor'),
                "boundElements": elem.get('boundElements', [])
            })

    return {
        "format": "excalidraw",
        "nodes": nodes,
        "edges": edges,
        "text_content": text_content,
        "app_state": data.get('appState', {}),
        "metadata": {
            "element_count": len(elements),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "version": data.get('version', 'unknown')
        }
    }


# ============================================================================
# SVG Parsing
# ============================================================================

def _read_svg(file_path: Path) -> dict:
    """Read and parse an SVG file."""
    content = file_path.read_text(encoding='utf-8')

    try:
        # Parse with namespace handling
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return {"error": f"Invalid SVG: {str(e)}"}

    # Get dimensions
    width = root.get('width', 'unknown')
    height = root.get('height', 'unknown')
    viewbox = root.get('viewBox', '')

    # Extract text content
    text_content = []
    for text_elem in root.iter():
        if text_elem.text and text_elem.text.strip():
            text_content.append(text_elem.text.strip())

    # Count shapes
    shape_counts = {}
    for elem in root.iter():
        tag = elem.tag.split('}')[-1]  # Remove namespace
        if tag in ('rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path', 'text', 'g'):
            shape_counts[tag] = shape_counts.get(tag, 0) + 1

    return {
        "format": "svg",
        "dimensions": {
            "width": width,
            "height": height,
            "viewBox": viewbox
        },
        "text_content": list(set(text_content)),
        "shape_counts": shape_counts,
        "metadata": {
            "total_elements": sum(shape_counts.values())
        }
    }


# ============================================================================
# Diagram Reading Tool
# ============================================================================

@mcp.tool()
def diagram_read(
    path: Annotated[str, Field(description="Path to diagram file relative to project directory")],
) -> str:
    """Read and parse a diagram file to extract its structure.

    Supports: .drawio, .excalidraw, .svg

    Returns JSON with:
    - format: The diagram format
    - nodes: List of shapes/elements
    - edges: List of connections
    - text_content: All text found in the diagram
    - metadata: Format-specific metadata

    Args:
        path: Path to the diagram file (relative to project directory)

    Returns:
        JSON string with diagram structure and metadata
    """
    try:
        file_path = _resolve_path(path)

        if not file_path.exists():
            return json.dumps({"error": f"File not found: {path}"})

        suffix = file_path.suffix.lower()

        if suffix in ('.drawio', '.xml'):
            result = _read_drawio(file_path)
        elif suffix == '.excalidraw':
            result = _read_excalidraw(file_path)
        elif suffix == '.svg':
            result = _read_svg(file_path)
        else:
            return json.dumps({
                "error": f"Unsupported format: {suffix}. Supported: .drawio, .excalidraw, .svg"
            })

        result["path"] = path
        return json.dumps(result, indent=2, default=str)

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to read diagram: {str(e)}"})


# ============================================================================
# Diagram Writing
# ============================================================================

def _create_drawio_xml(nodes: list, edges: list, name: str = "Page-1") -> str:
    """Create a draw.io XML structure from nodes and edges."""
    # Create mxfile structure
    mxfile = ET.Element('mxfile', {
        'host': 'mcp-diagram-tools',
        'modified': '',
        'agent': 'MCP Diagram Tools',
        'version': '1.0'
    })

    diagram = ET.SubElement(mxfile, 'diagram', {
        'name': name,
        'id': 'diagram-1'
    })

    mxgraph = ET.SubElement(diagram, 'mxGraphModel', {
        'dx': '0',
        'dy': '0',
        'grid': '1',
        'gridSize': '10',
        'guides': '1',
        'tooltips': '1',
        'connect': '1',
        'arrows': '1',
        'fold': '1',
        'page': '1',
        'pageScale': '1',
        'pageWidth': '850',
        'pageHeight': '1100'
    })

    root_elem = ET.SubElement(mxgraph, 'root')

    # Add required root cells
    ET.SubElement(root_elem, 'mxCell', {'id': '0'})
    ET.SubElement(root_elem, 'mxCell', {'id': '1', 'parent': '0'})

    # Add nodes
    for i, node in enumerate(nodes):
        node_id = node.get('id', f'node-{i+2}')
        label = node.get('label', '')
        style = node.get('style', 'rounded=1;whiteSpace=wrap;html=1;')
        geo = node.get('geometry', {})

        cell = ET.SubElement(root_elem, 'mxCell', {
            'id': node_id,
            'value': label,
            'style': style,
            'vertex': '1',
            'parent': '1'
        })

        ET.SubElement(cell, 'mxGeometry', {
            'x': str(geo.get('x', i * 150)),
            'y': str(geo.get('y', 100)),
            'width': str(geo.get('width', 120)),
            'height': str(geo.get('height', 60)),
            'as': 'geometry'
        })

    # Add edges
    for i, edge in enumerate(edges):
        edge_id = edge.get('id', f'edge-{i+100}')
        source = edge.get('source', '')
        target = edge.get('target', '')
        label = edge.get('label', '')
        style = edge.get('style', 'edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;')

        cell = ET.SubElement(root_elem, 'mxCell', {
            'id': edge_id,
            'value': label,
            'style': style,
            'edge': '1',
            'parent': '1',
            'source': source,
            'target': target
        })

        ET.SubElement(cell, 'mxGeometry', {
            'relative': '1',
            'as': 'geometry'
        })

    return ET.tostring(mxfile, encoding='unicode', xml_declaration=True)


def _generate_curved_points(dx: float, dy: float, curve_direction: str = "auto") -> list:
    """Generate 3-point curved path with midpoint offset perpendicular to line.

    Args:
        dx: Horizontal distance to end point
        dy: Vertical distance to end point
        curve_direction: "auto", "up", "down", "left", "right"
            - "up": curve arcs upward (negative y offset)
            - "down": curve arcs downward (positive y offset)
            - "left": curve arcs left (negative x offset)
            - "right": curve arcs right (positive x offset)
            - "auto": automatically determine based on direction
    """
    mid_x = dx / 2
    mid_y = dy / 2
    # Use 20% of the longer dimension as curve offset
    offset = max(abs(dx), abs(dy)) * 0.2

    if curve_direction == "up":
        return [[0, 0], [mid_x, mid_y - offset], [dx, dy]]
    elif curve_direction == "down":
        return [[0, 0], [mid_x, mid_y + offset], [dx, dy]]
    elif curve_direction == "left":
        return [[0, 0], [mid_x - offset, mid_y], [dx, dy]]
    elif curve_direction == "right":
        return [[0, 0], [mid_x + offset, mid_y], [dx, dy]]
    else:
        # Auto: offset perpendicular to line
        if abs(dx) > abs(dy):
            # Horizontal-dominant: curve vertically (down by default)
            return [[0, 0], [mid_x, mid_y + offset], [dx, dy]]
        else:
            # Vertical-dominant: curve horizontally
            return [[0, 0], [mid_x - offset, mid_y], [dx, dy]]


def _generate_step_points(dx: float, dy: float) -> list:
    """Generate 3-point step/elbow path (right angle bend)."""
    if abs(dy) > abs(dx):
        # Vertical-dominant: go down first, then across
        return [[0, 0], [0, dy], [dx, dy]]
    else:
        # Horizontal-dominant: go across first, then down
        return [[0, 0], [dx, 0], [dx, dy]]


def _create_excalidraw_json(nodes: list, edges: list) -> str:
    """Create an Excalidraw JSON structure from nodes and edges."""
    # Use proper millisecond timestamp for updated field
    timestamp = int(time.time() * 1000)

    def gen_id():
        return ''.join(random.choices(string.ascii_letters + string.digits, k=21))

    elements = []
    # Track elements by ID for later binding updates (arrows to shapes)
    element_map = {}
    # Track arrow bindings to update shapes' boundElements after all arrows created
    arrow_bindings = []  # List of (arrow_id, source_id, target_id)

    # Add nodes
    for i, node in enumerate(nodes):
        elem_id = node.get('id', gen_id())
        node_type = node.get('type', 'rectangle')
        label = node.get('label', node.get('text', ''))

        if node_type == 'text':
            text_elem = {
                "id": elem_id,
                "type": "text",
                "x": node.get('x', i * 150),
                "y": node.get('y', 100),
                "width": node.get('width', 100),
                "height": node.get('height', 25),
                "text": label,
                "fontSize": node.get('fontSize', 16),
                "fontFamily": 1,
                "textAlign": "center",
                "verticalAlign": "middle",
                "strokeColor": node.get('strokeColor', '#1e1e1e'),
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "roughness": 1,
                "opacity": 100,
                "angle": 0,
                "seed": random.randint(1, 999999),
                "version": 1,
                "versionNonce": random.randint(1, 999999),
                "isDeleted": False,
                "groupIds": [],
                "frameId": None,
                "boundElements": [],
                "updated": timestamp,
                "link": None,
                "locked": False,
                "containerId": None,
                "originalText": label,
                "autoResize": True,
                "lineHeight": 1.25
            }
            elements.append(text_elem)
            element_map[elem_id] = text_elem
        else:
            # Generate predictable text ID for bound label
            text_id = f"{elem_id}_text" if label else None

            # Create the shape element with bound text reference
            shape_elem = {
                "id": elem_id,
                "type": node_type,
                "x": node.get('x', i * 150),
                "y": node.get('y', 100),
                "width": node.get('width', 120),
                "height": node.get('height', 60),
                "strokeColor": node.get('strokeColor', '#1e1e1e'),
                "backgroundColor": node.get('backgroundColor', 'transparent'),
                "fillStyle": node.get('fillStyle', 'solid'),
                "strokeWidth": node.get('strokeWidth', 2),
                "roughness": node.get('roughness', 1),
                "opacity": 100,
                "angle": 0,
                "seed": random.randint(1, 999999999),
                "version": 1,
                "versionNonce": random.randint(1, 999999999),
                "isDeleted": False,
                "strokeStyle": node.get('strokeStyle', 'solid'),
                "groupIds": [],
                "frameId": None,
                "roundness": {"type": 3} if node.get('rounded', True) and node_type == 'rectangle' else None,
                # Bind text label to this shape (arrows added later)
                "boundElements": [{"type": "text", "id": text_id}] if text_id else [],
                "updated": timestamp,
                "link": None,
                "locked": False
            }
            elements.append(shape_elem)
            element_map[elem_id] = shape_elem

            # Create bound text element (with containerId linking to shape)
            if label:
                shape_x = node.get('x', i * 150)
                shape_y = node.get('y', 100)
                shape_w = node.get('width', 120)
                shape_h = node.get('height', 60)

                # Calculate font size based on label length and shape size
                base_font_size = node.get('fontSize', 16)
                if len(label) > 30:
                    base_font_size = min(base_font_size, 12)
                elif len(label) > 50:
                    base_font_size = min(base_font_size, 10)

                # For bound text, Excalidraw positions based on container + alignment
                text_elem = {
                    "id": text_id,
                    "type": "text",
                    "x": shape_x,
                    "y": shape_y,
                    "width": shape_w,
                    "height": shape_h,
                    "text": label,
                    "fontSize": base_font_size,
                    "fontFamily": 1,
                    "textAlign": "center",
                    "verticalAlign": "middle",
                    "strokeColor": node.get('textColor', '#1e1e1e'),
                    "backgroundColor": "transparent",
                    "fillStyle": "solid",
                    "strokeWidth": 1,
                    "roughness": 1,
                    "opacity": 100,
                    "angle": 0,
                    "seed": random.randint(1, 999999999),
                    "version": 1,
                    "versionNonce": random.randint(1, 999999999),
                    "isDeleted": False,
                    "groupIds": [],
                    "frameId": None,
                    "boundElements": [],
                    "updated": timestamp,
                    "link": None,
                    "locked": False,
                    "containerId": elem_id,
                    "originalText": label,
                    "autoResize": True,
                    "lineHeight": 1.25
                }
                elements.append(text_elem)

    # Build node lookup for edge positioning
    node_lookup = {n.get('id'): n for n in nodes if n.get('id')}

    # Add edges as arrows
    for i, edge in enumerate(edges):
        arrow_id = edge.get('id', gen_id())
        edge_label = edge.get('label', '')

        # Calculate arrow position based on source/target nodes if available
        arrow_x = edge.get('x', 0)
        arrow_y = edge.get('y', 130)
        points = edge.get('points', [[0, 0], [100, 0]])

        source_id = edge.get('source')
        target_id = edge.get('target')

        dx = 0
        dy = 0

        if source_id and target_id and source_id in node_lookup and target_id in node_lookup:
            src = node_lookup[source_id]
            tgt = node_lookup[target_id]

            src_x = src.get('x', 0)
            src_y = src.get('y', 0)
            src_w = src.get('width', 120)
            src_h = src.get('height', 60)
            tgt_x = tgt.get('x', 0)
            tgt_y = tgt.get('y', 0)
            tgt_w = tgt.get('width', 120)
            tgt_h = tgt.get('height', 60)

            # Calculate node centers
            src_cx = src_x + src_w / 2
            src_cy = src_y + src_h / 2
            tgt_cx = tgt_x + tgt_w / 2
            tgt_cy = tgt_y + tgt_h / 2

            dx = tgt_cx - src_cx
            dy = tgt_cy - src_cy

            # Get explicit attachment sides if specified
            start_side = edge.get('startSide')  # "top", "bottom", "left", "right"
            end_side = edge.get('endSide')

            # Calculate start point based on startSide or auto-detect
            if start_side == 'bottom':
                arrow_start_x = src_cx
                arrow_start_y = src_y + src_h
            elif start_side == 'top':
                arrow_start_x = src_cx
                arrow_start_y = src_y
            elif start_side == 'left':
                arrow_start_x = src_x
                arrow_start_y = src_cy
            elif start_side == 'right':
                arrow_start_x = src_x + src_w
                arrow_start_y = src_cy
            else:
                # Auto-detect based on direction
                if abs(dx) > abs(dy):
                    arrow_start_x = src_x + src_w if dx > 0 else src_x
                    arrow_start_y = src_cy
                else:
                    arrow_start_x = src_cx
                    arrow_start_y = src_y + src_h if dy > 0 else src_y

            # Calculate end point based on endSide or auto-detect
            if end_side == 'top':
                arrow_end_x = tgt_cx
                arrow_end_y = tgt_y
            elif end_side == 'bottom':
                arrow_end_x = tgt_cx
                arrow_end_y = tgt_y + tgt_h
            elif end_side == 'left':
                arrow_end_x = tgt_x
                arrow_end_y = tgt_cy
            elif end_side == 'right':
                arrow_end_x = tgt_x + tgt_w
                arrow_end_y = tgt_cy
            else:
                # Auto-detect based on direction
                if abs(dx) > abs(dy):
                    arrow_end_x = tgt_x if dx > 0 else tgt_x + tgt_w
                    arrow_end_y = tgt_cy
                else:
                    arrow_end_x = tgt_cx
                    arrow_end_y = tgt_y if dy > 0 else tgt_y + tgt_h

            arrow_x = arrow_start_x
            arrow_y = arrow_start_y

            # Calculate end point delta
            end_dx = arrow_end_x - arrow_start_x
            end_dy = arrow_end_y - arrow_start_y

            # Generate points based on curveStyle (if not using explicit points)
            if not edge.get('points'):
                curve_style = edge.get('curveStyle', 'straight')
                curve_direction = edge.get('curveDirection', 'auto')
                if curve_style == 'curved':
                    points = _generate_curved_points(end_dx, end_dy, curve_direction)
                elif curve_style == 'step':
                    points = _generate_step_points(end_dx, end_dy)
                else:
                    points = [[0, 0], [end_dx, end_dy]]

        # Generate text ID if there's a label
        edge_text_id = gen_id() if edge_label else None

        # Support dashed lines via strokeStyle
        stroke_style = edge.get('strokeStyle', 'solid')

        # Create arrow bindings to connect to shapes
        start_binding = None
        end_binding = None

        if source_id and target_id and source_id in node_lookup and target_id in node_lookup:
            if abs(dx) > abs(dy):
                start_focus = 0.5 if dx > 0 else -0.5
                end_focus = -0.5 if dx > 0 else 0.5
            else:
                start_focus = 0.5 if dy > 0 else -0.5
                end_focus = -0.5 if dy > 0 else 0.5

            start_binding = {
                "elementId": source_id,
                "focus": start_focus,
                "gap": 8
            }
            end_binding = {
                "elementId": target_id,
                "focus": end_focus,
                "gap": 8
            }
            arrow_bindings.append((arrow_id, source_id, target_id))

        # Determine if arrow should be curved (smooth through waypoints)
        curve_style = edge.get('curveStyle', 'straight')
        is_curved = curve_style == 'curved' or len(points) > 2

        arrow = {
            "id": arrow_id,
            "type": "arrow",
            "x": arrow_x,
            "y": arrow_y,
            "width": abs(points[-1][0]) if points else 100,
            "height": abs(points[-1][1]) if points else 0,
            "strokeColor": edge.get('strokeColor', '#1e1e1e'),
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": edge.get('strokeWidth', 2),
            "roughness": 1,
            "opacity": 100,
            "angle": 0,
            "seed": random.randint(1, 999999),
            "version": 1,
            "versionNonce": random.randint(1, 999999),
            "isDeleted": False,
            "strokeStyle": stroke_style,
            "groupIds": [],
            "frameId": None,
            "roundness": {"type": 2} if is_curved else None,
            "boundElements": [{"id": edge_text_id, "type": "text"}] if edge_text_id else [],
            "updated": timestamp,
            "link": None,
            "locked": False,
            "points": points,
            "startBinding": start_binding,
            "endBinding": end_binding,
            "startArrowhead": edge.get('startArrowhead', None),
            "endArrowhead": edge.get('endArrowhead', 'arrow'),
            "elbowed": False
        }
        elements.append(arrow)

        # Add edge label as text element
        if edge_label:
            mid_x = arrow_x + (points[-1][0] / 2) if points else arrow_x + 50
            mid_y = arrow_y + (points[-1][1] / 2) - 15 if points else arrow_y - 15

            edge_text = {
                "id": edge_text_id,
                "type": "text",
                "x": mid_x,
                "y": mid_y,
                "width": len(edge_label) * 8,
                "height": 20,
                "text": edge_label,
                "fontSize": 14,
                "fontFamily": 1,
                "textAlign": "center",
                "verticalAlign": "middle",
                "strokeColor": "#1e1e1e",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "roughness": 1,
                "opacity": 100,
                "angle": 0,
                "seed": random.randint(1, 999999),
                "version": 1,
                "versionNonce": random.randint(1, 999999),
                "isDeleted": False,
                "groupIds": [],
                "frameId": None,
                "boundElements": [],
                "updated": timestamp,
                "link": None,
                "locked": False,
                "containerId": arrow_id,
                "originalText": edge_label,
                "autoResize": True,
                "lineHeight": 1.25
            }
            elements.append(edge_text)

    # Update shapes' boundElements to include connected arrows
    for arrow_id, source_id, target_id in arrow_bindings:
        if source_id and source_id in element_map:
            element_map[source_id]["boundElements"].append({"type": "arrow", "id": arrow_id})
        if target_id and target_id in element_map:
            element_map[target_id]["boundElements"].append({"type": "arrow", "id": arrow_id})

    return json.dumps({
        "type": "excalidraw",
        "version": 2,
        "source": "mcp-diagram-tools",
        "elements": elements,
        "appState": {
            "gridSize": None,
            "viewBackgroundColor": "#ffffff"
        },
        "files": {}
    }, indent=2)


def _create_svg(nodes: list, edges: list, width: int = 800, height: int = 600) -> str:
    """Create an SVG from nodes and edges."""
    # Calculate bounds
    min_x = min((n.get('x', 0) for n in nodes), default=0)
    min_y = min((n.get('y', 0) for n in nodes), default=0)
    max_x = max((n.get('x', 0) + n.get('width', 120) for n in nodes), default=width)
    max_y = max((n.get('y', 0) + n.get('height', 60) for n in nodes), default=height)

    # Add padding
    padding = 50
    view_width = max(width, max_x - min_x + padding * 2)
    view_height = max(height, max_y - min_y + padding * 2)

    svg_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{view_width}" height="{view_height}" viewBox="0 0 {view_width} {view_height}">',
        '  <defs>',
        '    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
        '      <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>',
        '    </marker>',
        '  </defs>',
        '  <rect width="100%" height="100%" fill="white"/>'
    ]

    # Add nodes
    for i, node in enumerate(nodes):
        x = node.get('x', i * 150) - min_x + padding
        y = node.get('y', 100) - min_y + padding
        w = node.get('width', 120)
        h = node.get('height', 60)
        label = node.get('label', node.get('text', ''))
        fill = node.get('backgroundColor', '#e1f5fe')
        stroke = node.get('strokeColor', '#0288d1')
        node_type = node.get('type', 'rectangle')

        if node_type == 'ellipse' or node_type == 'circle':
            cx = x + w/2
            cy = y + h/2
            rx = w/2
            ry = h/2
            svg_parts.append(f'  <ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        elif node_type == 'diamond':
            points = f"{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}"
            svg_parts.append(f'  <polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        else:
            # Rectangle (default)
            svg_parts.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

        # Add label
        if label:
            text_x = x + w/2
            text_y = y + h/2 + 5
            svg_parts.append(f'  <text x="{text_x}" y="{text_y}" text-anchor="middle" font-family="Arial" font-size="14" fill="#333">{label}</text>')

    # Create node lookup for edge positioning
    node_lookup = {n.get('id', f'node-{i}'): n for i, n in enumerate(nodes)}

    # Add edges
    for edge in edges:
        source_id = edge.get('source')
        target_id = edge.get('target')
        label = edge.get('label', '')

        if source_id and target_id and source_id in node_lookup and target_id in node_lookup:
            src = node_lookup[source_id]
            tgt = node_lookup[target_id]

            x1 = src.get('x', 0) - min_x + padding + src.get('width', 120)
            y1 = src.get('y', 100) - min_y + padding + src.get('height', 60) / 2
            x2 = tgt.get('x', 0) - min_x + padding
            y2 = tgt.get('y', 100) - min_y + padding + tgt.get('height', 60) / 2

            svg_parts.append(f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="2" marker-end="url(#arrowhead)"/>')

            if label:
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2 - 10
                svg_parts.append(f'  <text x="{mid_x}" y="{mid_y}" text-anchor="middle" font-family="Arial" font-size="12" fill="#666">{label}</text>')

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


@mcp.tool()
def diagram_write(
    path: Annotated[str, Field(description="Output path relative to project directory")],
    nodes: Annotated[str, Field(description="JSON array of nodes: [{id, label, type, x, y, width, height}]")],
    edges: Annotated[str, Field(description="JSON array of edges: [{id, source, target, label, curveStyle?, points?}]")] = "[]",
    name: Annotated[Optional[str], Field(description="Diagram name (for multi-page formats)")] = None,
) -> str:
    """Create a new diagram from a structure definition.

    Format is inferred from the file extension.
    Supports: .drawio, .excalidraw, .svg

    Node structure:
    - id: Unique identifier (optional, auto-generated if not provided)
    - label/text: Display text
    - type: Shape type (rectangle, ellipse, diamond, text)
    - x, y: Position coordinates
    - width, height: Dimensions
    - backgroundColor, strokeColor: Colors

    Edge structure:
    - id: Unique identifier (optional)
    - source: Source node ID
    - target: Target node ID
    - label: Edge label
    - curveStyle: Line style - "straight" (default), "curved", or "step"
    - curveDirection: For curved lines - "auto", "up", "down", "left", "right"
    - startSide: Attachment side on source - "top", "bottom", "left", "right" (auto if omitted)
    - endSide: Attachment side on target - "top", "bottom", "left", "right" (auto if omitted)
    - points: Custom waypoints array [[x1,y1], [x2,y2], ...] (relative coords)
    - strokeStyle: "solid" (default) or "dashed"
    - strokeColor, strokeWidth: Line appearance

    Args:
        path: Output file path (relative to project directory)
        nodes: JSON array of node definitions
        edges: JSON array of edge definitions
        name: Optional diagram/page name

    Returns:
        JSON string with success status and path
    """
    try:
        file_path = _resolve_path(path)
        suffix = file_path.suffix.lower()

        # Parse nodes and edges
        try:
            nodes_list = json.loads(nodes) if isinstance(nodes, str) else nodes
            edges_list = json.loads(edges) if isinstance(edges, str) else edges
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {str(e)}"})

        if suffix == '.drawio' or suffix == '.xml':
            content = _create_drawio_xml(nodes_list, edges_list, name or "Page-1")
        elif suffix == '.excalidraw':
            content = _create_excalidraw_json(nodes_list, edges_list)
        elif suffix == '.svg':
            content = _create_svg(nodes_list, edges_list)
        else:
            return json.dumps({
                "error": f"Unsupported format for writing: {suffix}. Supported: .drawio, .excalidraw, .svg"
            })

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')

        return json.dumps({
            "success": True,
            "path": str(file_path.relative_to(PROJECT_DIR)),
            "format": suffix.lstrip('.'),
            "node_count": len(nodes_list),
            "edge_count": len(edges_list)
        }, indent=2)

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to write diagram: {str(e)}"})


# ============================================================================
# Diagram Rendering
# ============================================================================

@mcp.tool()
async def diagram_render(
    path: Annotated[str, Field(description="Path to diagram file")],
    output_path: Annotated[str, Field(description="Output PNG/SVG path")],
    width: Annotated[int, Field(description="Output width in pixels")] = 1200,
    height: Annotated[int, Field(description="Output height in pixels")] = 800,
) -> str:
    """Render a diagram to PNG or SVG for visual verification.

    Supports rendering:
    - .drawio -> PNG/SVG
    - .excalidraw -> PNG/SVG
    - .svg -> PNG

    Uses headless browser rendering for accurate output.

    Args:
        path: Source diagram file path
        output_path: Output image path (.png or .svg)
        width: Output width in pixels (default: 1200)
        height: Output height in pixels (default: 800)

    Returns:
        JSON string with success status and output path
    """
    try:
        source = _resolve_path(path)
        target = _resolve_path(output_path)

        if not source.exists():
            return json.dumps({"error": f"Source file not found: {path}"})

        source_ext = source.suffix.lower()
        target_ext = target.suffix.lower()

        target.parent.mkdir(parents=True, exist_ok=True)

        # For SVG to PNG, use cairosvg
        if source_ext == '.svg' and target_ext == '.png':
            try:
                import cairosvg
            except ImportError:
                return json.dumps({"error": "cairosvg not installed. Run: pip install cairosvg"})

            cairosvg.svg2png(
                url=str(source),
                write_to=str(target),
                output_width=width,
                output_height=height
            )

            return json.dumps({
                "success": True,
                "source": path,
                "output": str(target.relative_to(PROJECT_DIR)),
                "method": "cairosvg"
            }, indent=2)

        # For drawio and excalidraw, use Playwright
        if source_ext in ('.drawio', '.xml', '.excalidraw'):
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                return json.dumps({"error": "playwright not installed. Run: pip install playwright && playwright install chromium"})

            content = source.read_text(encoding='utf-8')

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": width, "height": height})

                if source_ext in ('.drawio', '.xml'):
                    html = _get_drawio_viewer_html(content, width, height)
                else:
                    html = _get_excalidraw_viewer_html(content, width, height)

                await page.set_content(html)
                await page.wait_for_timeout(2000)

                if target_ext == '.png':
                    await page.screenshot(path=str(target), full_page=False)
                elif target_ext == '.svg':
                    svg_content = await page.evaluate('''() => {
                        const svg = document.querySelector('svg');
                        return svg ? svg.outerHTML : null;
                    }''')
                    if svg_content:
                        target.write_text(svg_content, encoding='utf-8')
                    else:
                        await page.screenshot(path=str(target.with_suffix('.png')), full_page=False)
                        return json.dumps({
                            "success": True,
                            "warning": "SVG extraction failed, created PNG instead",
                            "output": str(target.with_suffix('.png').relative_to(PROJECT_DIR))
                        }, indent=2)

                await browser.close()

            return json.dumps({
                "success": True,
                "source": path,
                "output": str(target.relative_to(PROJECT_DIR)),
                "dimensions": {"width": width, "height": height},
                "method": "playwright"
            }, indent=2)

        return json.dumps({
            "error": f"Unsupported rendering: {source_ext} -> {target_ext}"
        })

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to render diagram: {str(e)}"})


def _get_drawio_viewer_html(diagram_xml: str, width: int, height: int) -> str:
    """Generate HTML that renders a draw.io diagram."""
    escaped_xml = json.dumps(diagram_xml)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ margin: 0; padding: 20px; background: white; }}
        #diagram {{ width: {width-40}px; height: {height-40}px; }}
    </style>
</head>
<body>
    <div id="diagram"></div>
    <script>
        const xmlStr = {escaped_xml};
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlStr, 'text/xml');

        const container = document.getElementById('diagram');
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', '{width-40}');
        svg.setAttribute('height', '{height-40}');
        svg.setAttribute('viewBox', '0 0 {width-40} {height-40}');

        const cells = xmlDoc.querySelectorAll('mxCell[vertex="1"], mxCell[value]');
        const edges = xmlDoc.querySelectorAll('mxCell[edge="1"]');

        cells.forEach((cell, idx) => {{
            const geo = cell.querySelector('mxGeometry');
            if (geo) {{
                const x = parseFloat(geo.getAttribute('x') || idx * 150);
                const y = parseFloat(geo.getAttribute('y') || 100);
                const w = parseFloat(geo.getAttribute('width') || 120);
                const h = parseFloat(geo.getAttribute('height') || 60);
                const value = cell.getAttribute('value') || '';

                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', x);
                rect.setAttribute('y', y);
                rect.setAttribute('width', w);
                rect.setAttribute('height', h);
                rect.setAttribute('fill', '#e1f5fe');
                rect.setAttribute('stroke', '#0288d1');
                rect.setAttribute('stroke-width', '2');
                rect.setAttribute('rx', '5');
                svg.appendChild(rect);

                if (value) {{
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', x + w/2);
                    text.setAttribute('y', y + h/2 + 5);
                    text.setAttribute('text-anchor', 'middle');
                    text.setAttribute('font-family', 'Arial');
                    text.setAttribute('font-size', '14');
                    text.textContent = value;
                    svg.appendChild(text);
                }}
            }}
        }});

        container.appendChild(svg);
    </script>
</body>
</html>'''


def _get_excalidraw_viewer_html(excalidraw_json: str, width: int, height: int) -> str:
    """Generate HTML that renders an Excalidraw diagram."""
    escaped_json = json.dumps(excalidraw_json)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ margin: 0; padding: 20px; background: white; }}
        #diagram {{ width: {width-40}px; height: {height-40}px; }}
    </style>
</head>
<body>
    <div id="diagram"></div>
    <script>
        const jsonStr = {escaped_json};
        const data = JSON.parse(jsonStr);

        const container = document.getElementById('diagram');
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', '{width-40}');
        svg.setAttribute('height', '{height-40}');
        svg.setAttribute('viewBox', '0 0 {width-40} {height-40}');

        const elements = data.elements || [];

        elements.forEach((elem) => {{
            const x = elem.x || 0;
            const y = elem.y || 0;
            const w = elem.width || 100;
            const h = elem.height || 50;
            const strokeColor = elem.strokeColor || '#000';
            const bgColor = elem.backgroundColor || 'transparent';

            if (elem.type === 'rectangle') {{
                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', x);
                rect.setAttribute('y', y);
                rect.setAttribute('width', w);
                rect.setAttribute('height', h);
                rect.setAttribute('fill', bgColor === 'transparent' ? '#fff' : bgColor);
                rect.setAttribute('stroke', strokeColor);
                rect.setAttribute('stroke-width', '2');
                svg.appendChild(rect);
            }} else if (elem.type === 'ellipse') {{
                const ellipse = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
                ellipse.setAttribute('cx', x + w/2);
                ellipse.setAttribute('cy', y + h/2);
                ellipse.setAttribute('rx', w/2);
                ellipse.setAttribute('ry', h/2);
                ellipse.setAttribute('fill', bgColor === 'transparent' ? '#fff' : bgColor);
                ellipse.setAttribute('stroke', strokeColor);
                ellipse.setAttribute('stroke-width', '2');
                svg.appendChild(ellipse);
            }} else if (elem.type === 'text') {{
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', x);
                text.setAttribute('y', y + 20);
                text.setAttribute('font-family', 'Arial');
                text.setAttribute('font-size', elem.fontSize || 20);
                text.setAttribute('fill', strokeColor);
                text.textContent = elem.text || '';
                svg.appendChild(text);
            }} else if (elem.type === 'arrow' || elem.type === 'line') {{
                const points = elem.points || [[0, 0], [100, 0]];
                if (points.length >= 2) {{
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', x + points[0][0]);
                    line.setAttribute('y1', y + points[0][1]);
                    line.setAttribute('x2', x + points[points.length-1][0]);
                    line.setAttribute('y2', y + points[points.length-1][1]);
                    line.setAttribute('stroke', strokeColor);
                    line.setAttribute('stroke-width', '2');
                    if (elem.type === 'arrow') {{
                        line.setAttribute('marker-end', 'url(#arrowhead)');
                    }}
                    svg.appendChild(line);
                }}
            }}
        }});

        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.innerHTML = '<marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#000"/></marker>';
        svg.insertBefore(defs, svg.firstChild);

        container.appendChild(svg);
    </script>
</body>
</html>'''


# ============================================================================
# Excalidraw Verification
# ============================================================================

@mcp.tool()
async def excalidraw_verify(
    path: Annotated[str, Field(description="Path to .excalidraw file to verify")],
) -> str:
    """Verify an Excalidraw file by rendering it with the real Excalidraw app.

    Uses excalidraw-brute-export-cli which runs the actual Excalidraw web app
    in a headless browser. This catches validation errors that would show as
    "invalid file" when opened in Excalidraw.

    Returns:
    - If valid: PNG image as base64 for visual verification
    - If invalid: Error message explaining why the file failed

    Args:
        path: Path to the .excalidraw file relative to project directory

    Returns:
        JSON string with verification result and base64 PNG if successful
    """
    import asyncio
    import tempfile

    try:
        source = _resolve_path(path)

        if not source.exists():
            return json.dumps({"error": f"File not found: {path}"})

        if source.suffix.lower() != '.excalidraw':
            return json.dumps({"error": f"Not an Excalidraw file: {path}"})

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            output_path = tmp.name

        try:
            cmd = [
                'npx', 'excalidraw-brute-export-cli',
                '-i', str(source),
                '--format', 'png',
                '--background', '1',
                '--scale', '1',
                '-o', output_path
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=60
            )

            if result.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else 'Unknown error'
                stdout_msg = stdout.decode('utf-8', errors='replace') if stdout else ''
                return json.dumps({
                    "valid": False,
                    "error": f"Excalidraw validation failed: {error_msg}",
                    "stdout": stdout_msg,
                    "stderr": error_msg,
                    "hint": "This file would show 'invalid file' error when opened in Excalidraw"
                }, indent=2)

            output_file = Path(output_path)
            if output_file.exists() and output_file.stat().st_size > 0:
                png_data = output_file.read_bytes()
                png_base64 = base64.b64encode(png_data).decode('ascii')

                return json.dumps({
                    "valid": True,
                    "message": "Excalidraw file is valid and renders correctly",
                    "image": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": png_base64
                    }
                }, indent=2)
            else:
                return json.dumps({
                    "valid": False,
                    "error": "Export completed but no output file was created"
                }, indent=2)

        finally:
            try:
                Path(output_path).unlink(missing_ok=True)
            except Exception:
                pass

    except asyncio.TimeoutError:
        return json.dumps({
            "valid": False,
            "error": "Timeout: Export took longer than 60 seconds"
        }, indent=2)
    except FileNotFoundError:
        return json.dumps({
            "valid": False,
            "error": "excalidraw-brute-export-cli not found. Ensure it's installed: npm install -g excalidraw-brute-export-cli"
        }, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({
            "valid": False,
            "error": f"Verification failed: {str(e)}"
        }, indent=2)


# ============================================================================
# Diagram Conversion
# ============================================================================

@mcp.tool()
def diagram_convert(
    source_path: Annotated[str, Field(description="Source diagram path")],
    target_path: Annotated[str, Field(description="Target diagram path")],
) -> str:
    """Convert diagram between formats.

    Supported conversions:
    - .drawio <-> .excalidraw (structure conversion)
    - .drawio/.excalidraw -> .svg (vector export)
    - Any -> .png (via diagram_render)

    Args:
        source_path: Source diagram file path
        target_path: Target diagram file path (format inferred from extension)

    Returns:
        JSON string with success status and output path
    """
    try:
        source = _resolve_path(source_path)
        target = _resolve_path(target_path)

        if not source.exists():
            return json.dumps({"error": f"Source file not found: {source_path}"})

        source_ext = source.suffix.lower()
        target_ext = target.suffix.lower()

        # Read source
        if source_ext in ('.drawio', '.xml'):
            result = _read_drawio(source)
            if "error" in result:
                return json.dumps(result)
            all_nodes = []
            all_edges = []
            for diag in result.get('diagrams', []):
                all_nodes.extend(diag.get('nodes', []))
                all_edges.extend(diag.get('edges', []))
        elif source_ext == '.excalidraw':
            result = _read_excalidraw(source)
            if "error" in result:
                return json.dumps(result)
            all_nodes = result.get('nodes', [])
            all_edges = result.get('edges', [])
        elif source_ext == '.svg':
            if target_ext != '.png':
                return json.dumps({"error": "SVG can only be converted to PNG"})
            try:
                import cairosvg
            except ImportError:
                return json.dumps({"error": "cairosvg not installed"})

            target.parent.mkdir(parents=True, exist_ok=True)
            cairosvg.svg2png(url=str(source), write_to=str(target))
            return json.dumps({
                "success": True,
                "source": source_path,
                "target": str(target.relative_to(PROJECT_DIR))
            }, indent=2)
        else:
            return json.dumps({"error": f"Unsupported source format: {source_ext}"})

        # Write to target format
        target.parent.mkdir(parents=True, exist_ok=True)

        if target_ext in ('.drawio', '.xml'):
            content = _create_drawio_xml(all_nodes, all_edges)
        elif target_ext == '.excalidraw':
            content = _create_excalidraw_json(all_nodes, all_edges)
        elif target_ext == '.svg':
            content = _create_svg(all_nodes, all_edges)
        elif target_ext == '.png':
            return json.dumps({
                "error": "For PNG output, use diagram_render tool instead"
            })
        else:
            return json.dumps({"error": f"Unsupported target format: {target_ext}"})

        target.write_text(content, encoding='utf-8')

        return json.dumps({
            "success": True,
            "source": source_path,
            "target": str(target.relative_to(PROJECT_DIR)),
            "nodes_converted": len(all_nodes),
            "edges_converted": len(all_edges)
        }, indent=2)

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Conversion failed: {str(e)}"})


# ============================================================================
# Mermaid to Excalidraw Conversion
# ============================================================================

@mcp.tool()
async def diagram_from_mermaid(
    path: Annotated[str, Field(description="Output path for the .excalidraw file (relative to project directory)")],
    mermaid_code: Annotated[str, Field(description="Mermaid diagram syntax (flowchart, sequence, etc.)")],
) -> str:
    """Create an Excalidraw diagram from Mermaid syntax.

    Mermaid handles layout automatically - no need to specify coordinates!
    This is ideal for flowcharts, sequence diagrams, and process flows.

    Supported Mermaid diagram types:
    - flowchart/graph (LR, TD, etc.)
    - sequence
    - class
    - state
    - er (entity relationship)

    Example Mermaid code:
    ```
    flowchart LR
        A[Start] --> B{Decision}
        B -->|Yes| C[Process]
        B -->|No| D[End]
        C --> D
    ```

    Args:
        path: Output file path ending in .excalidraw
        mermaid_code: Mermaid diagram syntax

    Returns:
        JSON string with success status and output path
    """
    import asyncio
    import tempfile

    try:
        file_path = _resolve_path(path)

        if not file_path.suffix.lower() == '.excalidraw':
            return json.dumps({
                "error": f"Output path must end with .excalidraw, got: {path}"
            })

        if not mermaid_code or not mermaid_code.strip():
            return json.dumps({
                "error": "mermaid_code cannot be empty"
            })

        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False, encoding='utf-8') as mmd_file:
            mmd_file.write(mermaid_code.strip())
            mmd_path = mmd_file.name

        with tempfile.NamedTemporaryFile(suffix='.excalidraw', delete=False) as out_file:
            out_path = out_file.name

        try:
            cmd = [
                'npx', '@excalidraw/mermaid-to-excalidraw',
                mmd_path,
                '-o', out_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60
                )
            except asyncio.TimeoutError:
                process.kill()
                return json.dumps({
                    "error": "Mermaid conversion timed out after 60 seconds"
                })

            stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ''
            stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ''

            if process.returncode != 0:
                return json.dumps({
                    "error": f"Mermaid conversion failed (exit {process.returncode})",
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "hint": "Check your Mermaid syntax at https://mermaid.live/"
                }, indent=2)

            out_file_path = Path(out_path)
            if not out_file_path.exists() or out_file_path.stat().st_size == 0:
                return json.dumps({
                    "error": "Conversion produced no output file",
                    "stdout": stdout_text,
                    "stderr": stderr_text
                })

            excalidraw_content = out_file_path.read_text(encoding='utf-8')

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(excalidraw_content, encoding='utf-8')

            try:
                data = json.loads(excalidraw_content)
                element_count = len(data.get('elements', []))
            except json.JSONDecodeError:
                element_count = 0

            return json.dumps({
                "success": True,
                "path": str(file_path.relative_to(PROJECT_DIR)),
                "format": "excalidraw",
                "element_count": element_count,
                "message": "Mermaid diagram converted successfully to Excalidraw format"
            }, indent=2)

        finally:
            try:
                Path(mmd_path).unlink(missing_ok=True)
                Path(out_path).unlink(missing_ok=True)
            except Exception:
                pass

    except FileNotFoundError:
        return json.dumps({
            "error": "@excalidraw/mermaid-to-excalidraw not found. Ensure it's installed: npm install -g @excalidraw/mermaid-to-excalidraw"
        })
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({
            "error": f"Mermaid conversion failed: {str(e)}"
        }, indent=2)
