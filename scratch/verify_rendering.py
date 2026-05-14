import sys
import os
import io
import json
import logging

# Add backend to path to import services
base_dir = r"c:\workspace\CCCTTNS\Hays_Resume_formater\Code\resume-formatter"
sys.path.append(os.path.join(base_dir, "backend"))

from app.services.resume_generator_service import ResumeGeneratorService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Input Data
resume_data = {
    "template_fill_result": {
        "candidate_full_name": {"value": "Divyang Panchasar", "marker_text": "«CandidateFullName»"},
        "work_experience": {
            "value": [
                {
                    "job_title": "Solution Architect",
                    "company": "Cognizant",
                    "location": "Bangalore",
                    "start_date": "MAY 2020",
                    "end_date": "PRESENT",
                    "responsibilities": "[:L1:]Led team of 12[:BR:]"
                }
            ],
            "marker_text": "«TableStart:WorkExperience»"
        }
    }
}

field_manifest = [
    {"fieldname": "candidate_full_name", "marker_text": "«CandidateFullName»", "field_type": "scalar"},
    {"fieldname": "work_experience", "marker_text": "«TableStart:WorkExperience»", "field_type": "table_loop", "loop_variable": "work_experience"}
]

# 2. Load Template (Absolute Path)
template_path = os.path.join(base_dir, "backend", ".data", "templates", "850c153b-c624-4bff-9b1c-24e4ed158d72", "FIN_BA_UK_Client_v1.docx")

if not os.path.exists(template_path):
    print(f"Error: Template not found at {template_path}")
    sys.exit(1)

with open(template_path, "rb") as f:
    template_bytes = f.read()

# 3. Generate
service = ResumeGeneratorService()
docx_bytes, missing = service.render_formatted_document(
    template_bytes=template_bytes,
    resume_data=resume_data,
    expected_fields="candidate_full_name,work_experience",
    field_manifest=field_manifest
)

# 4. Save Result
output_path = os.path.join(base_dir, "scratch", "verified_resume.docx")
with open(output_path, "wb") as f:
    f.write(docx_bytes)

print(f"Verification complete! Output saved to {output_path}")
