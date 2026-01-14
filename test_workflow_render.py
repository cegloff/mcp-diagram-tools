#!/usr/bin/env python3
"""Test script to render workflow diagram with the improved CLI renderer."""

import sys
sys.path.insert(0, 'src')

import asyncio
import json
from mcp_diagram_tools.server import diagram_write

nodes = [
    {"id": "intake", "label": "Intake", "type": "rectangle", "x": 50, "y": 100, "width": 100, "height": 50, "rounded": True},
    {"id": "pain_points", "label": "Pain Points\n\"this hurts\"", "type": "rectangle", "x": 200, "y": 100, "width": 120, "height": 50},
    {"id": "discovery", "label": "Discovery Process\n1-3x\n30 min session", "type": "rectangle", "x": 380, "y": 85, "width": 150, "height": 80},
    {"id": "aop", "label": "Art of the Possible\n(AOP) Document", "type": "rectangle", "x": 600, "y": 100, "width": 140, "height": 50},
    {"id": "roadmap", "label": "Customer Roadmap", "type": "rectangle", "x": 600, "y": 10, "width": 150, "height": 40},
    {"id": "socialize", "label": "Socialize/Iterate", "type": "rectangle", "x": 50, "y": 250, "width": 130, "height": 50, "rounded": True},
    {"id": "sow_gen", "label": "Statement of Work\nGeneration", "type": "rectangle", "x": 230, "y": 250, "width": 150, "height": 50},
    {"id": "negotiation", "label": "Negotiation\n(if needed)", "type": "rectangle", "x": 430, "y": 250, "width": 120, "height": 50},
    {"id": "signed_sow", "label": "Signed SOW", "type": "rectangle", "x": 620, "y": 250, "width": 120, "height": 50},
    {"id": "project_plan", "label": "Project Plan/\nImplementation Details", "type": "rectangle", "x": 50, "y": 400, "width": 160, "height": 60, "rounded": True},
    {"id": "followup", "label": "Project Follow-up\nFollow through", "type": "rectangle", "x": 280, "y": 400, "width": 150, "height": 60},
    {"id": "next_phase", "label": "Next phase of work (if identified)", "type": "rectangle", "x": 520, "y": 370, "width": 220, "height": 40},
    {"id": "ignite", "label": "Ignite Enablement", "type": "rectangle", "x": 520, "y": 450, "width": 150, "height": 40},
]

edges = [
    {"id": "e1", "source": "intake", "target": "pain_points", "label": ""},
    {"id": "e2", "source": "pain_points", "target": "discovery", "label": ""},
    {"id": "e3", "source": "discovery", "target": "aop", "label": ""},
    {"id": "e4", "source": "discovery", "target": "roadmap", "label": "", "strokeStyle": "dashed"},
    {"id": "e5", "source": "socialize", "target": "sow_gen", "label": ""},
    {"id": "e6", "source": "sow_gen", "target": "negotiation", "label": ""},
    {"id": "e7", "source": "negotiation", "target": "signed_sow", "label": ""},
    {"id": "e8", "source": "project_plan", "target": "followup", "label": ""},
    {"id": "e9", "source": "followup", "target": "next_phase", "label": "", "strokeStyle": "dashed"},
    {"id": "e10", "source": "followup", "target": "ignite", "label": "", "strokeStyle": "dashed"},
    {"id": "e11", "source": "aop", "target": "socialize", "label": "", "curveStyle": "curved", "startSide": "bottom", "endSide": "top", "curveDirection": "up"},
    {"id": "e12", "source": "signed_sow", "target": "project_plan", "label": "", "curveStyle": "curved", "startSide": "bottom", "endSide": "top", "curveDirection": "up"},
]

async def main():
    result = await diagram_write(
        path="workflow_rendered.excalidraw",
        nodes=json.dumps(nodes),
        edges=json.dumps(edges),
        name="Business Process Workflow",
        render=True
    )
    result_dict = json.loads(result)

    success = result_dict.get("success", False)
    node_count = result_dict.get("node_count", 0)
    edge_count = result_dict.get("edge_count", 0)

    print(f"Success: {success}")
    print(f"Nodes: {node_count}, Edges: {edge_count}")

    if "image" in result_dict:
        import base64
        png_data = base64.b64decode(result_dict["image"]["data"])
        with open("workflow_rendered.png", "wb") as f:
            f.write(png_data)
        print(f"Image saved: workflow_rendered.png ({len(png_data)} bytes)")
    elif "render_error" in result_dict:
        print(f"Render error: {result_dict['render_error']}")

if __name__ == "__main__":
    asyncio.run(main())
