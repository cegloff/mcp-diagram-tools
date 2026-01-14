#!/usr/bin/env python3
"""Test script to convert covid.png flowchart to Excalidraw."""

import sys
sys.path.insert(0, 'src')

import asyncio
from mcp_diagram_tools.server import diagram_write
import json

# Based on covid.png - COVID-19 testing decision flowchart

nodes = [
    # Left side - symptom checklist (not connected to main flow)
    {"id": "symptoms_title", "label": "ARE YOU EXPERIENCING\nTHESE SYMPTOMS?", "type": "rectangle", "x": 50, "y": 120, "width": 200, "height": 70, "backgroundColor": "#4a7cb5", "strokeColor": "#4a7cb5", "rounded": True},
    {"id": "fever", "label": "FEVER", "type": "rectangle", "x": 50, "y": 220, "width": 150, "height": 40, "backgroundColor": "#ffffff", "strokeColor": "#cccccc"},
    {"id": "coughing", "label": "COUGHING", "type": "rectangle", "x": 50, "y": 270, "width": 150, "height": 40, "backgroundColor": "#ffffff", "strokeColor": "#cccccc"},
    {"id": "breath", "label": "SHORTNESS\nOF BREATH", "type": "rectangle", "x": 50, "y": 320, "width": 150, "height": 50, "backgroundColor": "#ffffff", "strokeColor": "#cccccc"},

    # Main flowchart
    {"id": "call_physician", "label": "CALL YOUR\nPHYSICIAN.", "type": "rectangle", "x": 320, "y": 120, "width": 130, "height": 70, "backgroundColor": "#4a7cb5", "strokeColor": "#4a7cb5"},

    {"id": "severe_symptoms", "label": "You didn't get an\nimmediate response,\n& you are experiencing\nSEVERE symptoms?", "type": "rectangle", "x": 520, "y": 110, "width": 180, "height": 90, "backgroundColor": "#e8f0f8", "strokeColor": "#4a7cb5"},

    {"id": "urgent_care_top", "label": "Get to your local\nurgent care/ER or\nCALL 9-1-1.", "type": "rectangle", "x": 770, "y": 120, "width": 140, "height": 70, "backgroundColor": "#ffffff", "strokeColor": "#4a7cb5"},

    {"id": "urgent_care_left", "label": "Get to your local\nurgent care/ER\nor CALL 9-1-1.", "type": "rectangle", "x": 320, "y": 280, "width": 130, "height": 80, "backgroundColor": "#e8f0f8", "strokeColor": "#4a7cb5"},

    {"id": "mild_symptoms", "label": "Doctor identifies MILD\nsymptoms and advises\nhome isolation.", "type": "rectangle", "x": 520, "y": 290, "width": 180, "height": 70, "backgroundColor": "#e8f0f8", "strokeColor": "#4a7cb5"},

    {"id": "isolate", "label": "ISOLATE/\nSTAY AT HOME.", "type": "rectangle", "x": 770, "y": 295, "width": 130, "height": 60, "backgroundColor": "#ffffff", "strokeColor": "#4a7cb5"},

    {"id": "specimen", "label": "Specimen is\ncollected via swab\nand sent to lab\nto be tested.", "type": "rectangle", "x": 320, "y": 420, "width": 130, "height": 90, "backgroundColor": "#4a7cb5", "strokeColor": "#4a7cb5"},

    {"id": "results", "label": "Doctor should\nhave test results\nwithin 24 HOURS.", "type": "rectangle", "x": 320, "y": 570, "width": 130, "height": 80, "backgroundColor": "#e8f0f8", "strokeColor": "#4a7cb5"},
]

edges = [
    # Main flow from symptoms to call physician
    {"id": "e1", "source": "symptoms_title", "target": "call_physician", "label": ""},

    # From call physician - two branches
    {"id": "e2", "source": "call_physician", "target": "severe_symptoms", "label": ""},
    {"id": "e3", "source": "call_physician", "target": "urgent_care_left", "label": "", "startSide": "bottom", "endSide": "top"},

    # Severe symptoms branch
    {"id": "e4", "source": "severe_symptoms", "target": "urgent_care_top", "label": ""},
    {"id": "e5", "source": "severe_symptoms", "target": "mild_symptoms", "label": "", "startSide": "bottom", "endSide": "top"},

    # Mild symptoms to isolate
    {"id": "e6", "source": "mild_symptoms", "target": "isolate", "label": ""},

    # Urgent care left branch - down to specimen
    {"id": "e7", "source": "urgent_care_left", "target": "specimen", "label": "", "startSide": "bottom", "endSide": "top"},

    # Specimen to results
    {"id": "e8", "source": "specimen", "target": "results", "label": "", "startSide": "bottom", "endSide": "top"},
]

# Convert to JSON strings as expected by the tool
nodes_json = json.dumps(nodes)
edges_json = json.dumps(edges)

async def main():
    # Call the diagram_write function with render=True to get PNG preview
    result = await diagram_write(
        path="covid_flowchart.excalidraw",
        nodes=nodes_json,
        edges=edges_json,
        name="COVID-19 Testing Flowchart",
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
        with open("covid_flowchart.png", "wb") as f:
            f.write(png_data)
        print(f"  Saved rendered image to: covid_flowchart.png")
    elif "render_error" in result_dict:
        print(f"  Render error: {result_dict['render_error']}")

if __name__ == "__main__":
    asyncio.run(main())
