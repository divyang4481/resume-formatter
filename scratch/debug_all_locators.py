import sys
import os
sys.path.append(os.path.abspath('backend'))
import json
from docx import Document
from app.services.document_marker_locator import DocumentMarkerLocator

import logging
logging.basicConfig(level=logging.INFO)

doc = Document(r'SampleData\templates\UK Worldwide London.docx')
with open(r'scratch\latest_job_data.json', 'r', encoding='utf-8') as f:
    job_data = json.load(f)

manifest = job_data.get('template_manifest', {})
render_context = job_data.get('transformed_data', {})
if isinstance(render_context, dict) and 'fields' in render_context:
    # Just mock up the render context based on the manifest
    pass

# We will just run the locator logic but dump any modifications
locator = DocumentMarkerLocator()

print("Manifest fields:")
for f in manifest.get("fields", []):
    print(" ", f.get("fieldname"), f.get("render_locator"))

# We mock up a render context so it triggers the logic
mock_render_context = {}
for f in manifest.get("fields", []):
    fieldname = f.get("fieldname")
    mock_render_context[fieldname] = "test value"
    mock_render_context[fieldname + "_str"] = "test value str"

locator.apply_render_locators(doc, manifest, mock_render_context)

# Check if WORK EXPERIENCE is still there
found = False
for p in doc.paragraphs:
    if "WORK EXPERIENCE" in p.text:
        found = True
        print("FOUND WORK EXPERIENCE in modified doc")
if not found:
    print("WORK EXPERIENCE IS GONE!")

