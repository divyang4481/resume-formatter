import sys
import os
sys.path.append(os.path.abspath('backend'))
from docx import Document
from app.services.document_marker_locator import DocumentMarkerLocator
import logging
logging.basicConfig(level=logging.INFO)

doc = Document(r'SampleData\templates\UK Worldwide London.docx')
locator = DocumentMarkerLocator()

manifest = {
    "fields": [
        {
            "fieldname": "skills",
            "marker_text": "SkillsList",
            "field_type": "list",
            "render_locator": {
                "strategy": "replace_section_body",
                "heading": "Skills"
            }
        },
        {
            "fieldname": "work_experience",
            "marker_text": "WorkExperience",
            "field_type": "list",
            "render_locator": {
                "strategy": "replace_section_body",
                "heading": "WORK EXPERIENCE"
            }
        }
    ]
}

context = {
    "skills": ["Python", "Docker"],
    "work_experience": ["Software Engineer"]
}

locator.apply_render_locators(doc, manifest, context)

doc.save(r'scratch\debug_logic_out.docx')

for i, p in enumerate(doc.paragraphs[:15]):
    print(f"Para {i}: text='{p.text}'")
