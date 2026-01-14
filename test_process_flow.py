#!/usr/bin/env python3
"""Test script to convert IMG_0202.png process flow chart to Excalidraw."""

import sys
sys.path.insert(0, 'src')

import asyncio
from mcp_diagram_tools.server import diagram_write
import json

# Based on IMG_0202.png - Manufacturing Process Flow Chart

nodes = [
    # Top section
    {"id": "rm_receipt", "label": "RM receipt", "type": "ellipse", "x": 200, "y": 50, "width": 120, "height": 50, "backgroundColor": "#40c057", "strokeColor": "#2f9e44"},

    {"id": "inspection", "label": "Inspection", "type": "rectangle", "x": 200, "y": 140, "width": 120, "height": 50, "backgroundColor": "#40c057", "strokeColor": "#2f9e44", "rounded": True},

    {"id": "bop_receipt", "label": "BOP /Packing\nMaterial receipt", "type": "ellipse", "x": 400, "y": 120, "width": 130, "height": 60, "backgroundColor": "#40c057", "strokeColor": "#2f9e44"},

    # Decision: Material OK?
    {"id": "material_ok", "label": "Material\nOK or\nNot ?", "type": "diamond", "x": 210, "y": 220, "width": 100, "height": 80, "backgroundColor": "#fd7e14", "strokeColor": "#e8590c"},

    # Send to supplier branch
    {"id": "send_supplier", "label": "Send to\nsupplier", "type": "rectangle", "x": 30, "y": 230, "width": 100, "height": 60, "backgroundColor": "#339af0", "strokeColor": "#1c7ed6"},

    # Material Storage
    {"id": "material_storage", "label": "Material\nStorage", "type": "rectangle", "x": 210, "y": 340, "width": 100, "height": 60, "backgroundColor": "#94d82d", "strokeColor": "#74b816"},

    # Production
    {"id": "production", "label": "Production", "type": "rectangle", "x": 200, "y": 440, "width": 120, "height": 50, "backgroundColor": "#40c057", "strokeColor": "#2f9e44", "rounded": True},

    # Decision: Are parts OK?
    {"id": "parts_ok", "label": "Are the\nparts\nok?", "type": "diamond", "x": 210, "y": 520, "width": 100, "height": 80, "backgroundColor": "#fd7e14", "strokeColor": "#e8590c"},

    # Scrap Yard
    {"id": "scrap_yard", "label": "Scrap\nYard", "type": "ellipse", "x": 80, "y": 620, "width": 100, "height": 50, "backgroundColor": "#fa5252", "strokeColor": "#e03131"},

    # Packaging & Labelling
    {"id": "packaging", "label": "Packaging &\nLabelling", "type": "rectangle", "x": 360, "y": 530, "width": 120, "height": 50, "backgroundColor": "#40c057", "strokeColor": "#2f9e44"},

    # Pre-Dispatch Inspection
    {"id": "pre_dispatch", "label": "Pre-\nDispatch\nInspection", "type": "rectangle", "x": 520, "y": 520, "width": 100, "height": 70, "backgroundColor": "#339af0", "strokeColor": "#1c7ed6"},

    # Decision: OK or Not? (for dispatch)
    {"id": "dispatch_ok", "label": "OK or\nNot ?", "type": "diamond", "x": 530, "y": 400, "width": 80, "height": 70, "backgroundColor": "#fd7e14", "strokeColor": "#e8590c"},

    # Despatch
    {"id": "despatch", "label": "Despatch", "type": "ellipse", "x": 520, "y": 290, "width": 100, "height": 50, "backgroundColor": "#fa5252", "strokeColor": "#e03131"},
]

edges = [
    # RM receipt to Inspection
    {"id": "e1", "source": "rm_receipt", "target": "inspection", "label": ""},

    # BOP receipt to Inspection
    {"id": "e2", "source": "bop_receipt", "target": "inspection", "label": ""},

    # Inspection to Material OK decision
    {"id": "e3", "source": "inspection", "target": "material_ok", "label": ""},

    # Material OK - Not OK branch to Send to supplier
    {"id": "e4", "source": "material_ok", "target": "send_supplier", "label": "Not OK", "startSide": "left", "endSide": "right"},

    # Material OK - OK branch to Material Storage
    {"id": "e5", "source": "material_ok", "target": "material_storage", "label": "OK", "startSide": "bottom", "endSide": "top"},

    # Material Storage to Production
    {"id": "e6", "source": "material_storage", "target": "production", "label": ""},

    # Production to Parts OK decision
    {"id": "e7", "source": "production", "target": "parts_ok", "label": ""},

    # Parts OK - Rework loop back to Production
    {"id": "e8", "source": "parts_ok", "target": "production", "label": "Rework", "startSide": "left", "endSide": "left", "curveStyle": "curved", "curveDirection": "left"},

    # Parts OK - Reject to Scrap Yard
    {"id": "e9", "source": "parts_ok", "target": "scrap_yard", "label": "Reject", "startSide": "bottom", "endSide": "top"},

    # Parts OK - OK to Packaging
    {"id": "e10", "source": "parts_ok", "target": "packaging", "label": "OK", "startSide": "right", "endSide": "left"},

    # Packaging to Pre-Dispatch Inspection
    {"id": "e11", "source": "packaging", "target": "pre_dispatch", "label": ""},

    # Pre-Dispatch to Dispatch OK decision
    {"id": "e12", "source": "pre_dispatch", "target": "dispatch_ok", "label": "", "startSide": "top", "endSide": "bottom"},

    # Dispatch OK - OK to Despatch
    {"id": "e13", "source": "dispatch_ok", "target": "despatch", "label": "OK", "startSide": "top", "endSide": "bottom"},

    # Dispatch OK - Not OK loop back (for disposal decision)
    {"id": "e14", "source": "dispatch_ok", "target": "production", "label": "Not OK", "startSide": "left", "endSide": "right", "curveStyle": "curved", "curveDirection": "up"},
]

# Convert to JSON strings as expected by the tool
nodes_json = json.dumps(nodes)
edges_json = json.dumps(edges)

async def main():
    # Call the diagram_write function with render=True to get PNG preview
    result = await diagram_write(
        path="process_flowchart.excalidraw",
        nodes=nodes_json,
        edges=edges_json,
        name="Process Flow Chart",
        render=True
    )

    result_dict = json.loads(result)

    print("Result:")
    print(f"  Success: {result_dict['success']}")
    print(f"  Path: {result_dict['path']}")
    print(f"  Node count: {result_dict['node_count']}")
    print(f"  Edge count: {result_dict['edge_count']}")

    if "image" in result_dict:
        print(f"  Image rendered: Yes ({len(result_dict['image']['data'])} chars base64)")

        # Save the rendered image
        import base64
        png_data = base64.b64decode(result_dict['image']['data'])
        with open("process_flowchart.png", "wb") as f:
            f.write(png_data)
        print(f"  Saved rendered image to: process_flowchart.png")
    elif "render_error" in result_dict:
        print(f"  Render error: {result_dict['render_error']}")

if __name__ == "__main__":
    asyncio.run(main())
