#!/usr/bin/env python3
"""Test script to convert image.png flowchart to Excalidraw."""

import sys
sys.path.insert(0, 'src')

from mcp_diagram_tools.server import diagram_write
import json

# Based on the image.png flowchart - a 3-phase business process workflow

# Phase 1: Discovery (Row 1)
# Phase 2: SOW (Row 2)
# Phase 3: Implementation (Row 3)

nodes = [
    # Row 1 - Discovery Phase
    {"id": "intake", "label": "Intake", "type": "rectangle", "x": 50, "y": 100, "width": 100, "height": 50, "rounded": True},
    {"id": "pain_points", "label": "Pain Points\n\"this hurts\"", "type": "rectangle", "x": 200, "y": 100, "width": 120, "height": 50},
    {"id": "discovery", "label": "Discovery Process\n1-3x\n30 min session", "type": "rectangle", "x": 380, "y": 85, "width": 150, "height": 80},
    {"id": "aop", "label": "Art of the Possible\n(AOP) Document", "type": "rectangle", "x": 600, "y": 100, "width": 140, "height": 50},
    {"id": "roadmap", "label": "Customer Roadmap", "type": "rectangle", "x": 600, "y": 10, "width": 150, "height": 40},

    # Row 2 - SOW Phase
    {"id": "socialize", "label": "Socialize/Iterate", "type": "rectangle", "x": 50, "y": 250, "width": 130, "height": 50, "rounded": True},
    {"id": "sow_gen", "label": "Statement of Work\nGeneration", "type": "rectangle", "x": 230, "y": 250, "width": 150, "height": 50},
    {"id": "negotiation", "label": "Negotiation\n(if needed)", "type": "rectangle", "x": 430, "y": 250, "width": 120, "height": 50},
    {"id": "signed_sow", "label": "Signed SOW", "type": "rectangle", "x": 620, "y": 250, "width": 120, "height": 50},

    # Row 3 - Implementation Phase
    {"id": "project_plan", "label": "Project Plan/\nImplementation Details", "type": "rectangle", "x": 50, "y": 400, "width": 160, "height": 60, "rounded": True},
    {"id": "followup", "label": "Project Follow-up\nFollow through", "type": "rectangle", "x": 280, "y": 400, "width": 150, "height": 60},
    {"id": "next_phase", "label": "Next phase of work (if identified)", "type": "rectangle", "x": 520, "y": 370, "width": 220, "height": 40},
    {"id": "ignite", "label": "Ignite Enablement", "type": "rectangle", "x": 520, "y": 450, "width": 150, "height": 40},
]

edges = [
    # Row 1 connections
    {"id": "e1", "source": "intake", "target": "pain_points", "label": ""},
    {"id": "e2", "source": "pain_points", "target": "discovery", "label": ""},
    {"id": "e3", "source": "discovery", "target": "aop", "label": ""},
    {"id": "e4", "source": "discovery", "target": "roadmap", "label": "", "strokeStyle": "dashed"},

    # Row 2 connections
    {"id": "e5", "source": "socialize", "target": "sow_gen", "label": ""},
    {"id": "e6", "source": "sow_gen", "target": "negotiation", "label": ""},
    {"id": "e7", "source": "negotiation", "target": "signed_sow", "label": "", "strokeStyle": "dashed"},

    # Row 3 connections
    {"id": "e8", "source": "project_plan", "target": "followup", "label": ""},
    {"id": "e9", "source": "followup", "target": "next_phase", "label": "", "strokeStyle": "dashed"},
    {"id": "e10", "source": "followup", "target": "ignite", "label": "", "strokeStyle": "dashed"},

    # Phase transitions (vertical connections between rows) - curved lines from bottom to top
    {"id": "e11", "source": "aop", "target": "socialize", "label": "", "curveStyle": "curved", "startSide": "bottom", "endSide": "top", "curveDirection": "up"},
    {"id": "e12", "source": "signed_sow", "target": "project_plan", "label": "", "curveStyle": "curved", "startSide": "bottom", "endSide": "top", "curveDirection": "up"},
]

# Convert to JSON strings as expected by the tool
nodes_json = json.dumps(nodes)
edges_json = json.dumps(edges)

# Call the diagram_write function
result = diagram_write(
    path="workflow.excalidraw",
    nodes=nodes_json,
    edges=edges_json,
    name="Business Process Workflow"
)

print("Result:")
print(result)
