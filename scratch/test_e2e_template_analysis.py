import asyncio
import os
import json
from dotenv import load_dotenv

# Load env vars for Bedrock credentials
load_dotenv()

from app.services.resume_ai_service import ResumeAiService
from app.adapters.llm.aws_bedrock_runtime import BedrockAdapter

class MockDoclingExtraction:
    async def extract(self, content, filename, mime_type):
        class MockDoc:
            extracted_text = "CANDIDATE PROFILE\nCandidate\nPosition Required\n[Type text]\nOur expert opinion\nCVcomments\nProfessional qualifications\nTableStart:bCheckType\nCheckType\nTableEnd:bCheckType\nKey skills\n[Type text]\nNotice period\nLiving in\nSalary required\nEmployeeEmail"
            structured_data = {}
        return MockDoc()

async def test_e2e_analysis():
    file_path = r"C:\Users\dpanc\Downloads\UK Telecoms.docx"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Initializing services...")
    llm = BedrockAdapter() 
    # Use mock for Docling to bypass local environment issues
    extraction = MockDoclingExtraction()
    ai_service = ResumeAiService(llm, extraction)

    print(f"Reading file: {file_path}")
    with open(file_path, "rb") as f:
        content = f.read()

    print("Running End-to-End Template Analysis (Mock Docling + REAL XML Scan + REAL LLM)...")
    # This will use the REAL _get_docx_placeholders_from_xml because we are using the real ResumeAiService
    result = await ai_service.analyze_template(content, "UK Telecoms.docx")
    
    print("\n--- FINAL TEMPLATE MANIFEST ---")
    print(json.dumps(result, indent=2))
    print("\n--- Verification ---")
    manifest = result.get("field_extraction_manifest", [])
    found_fields = [str(m) for m in manifest]
    
    # We expect these to be found by the REAL XML scan even if the mock docling text doesn't have them
    critical_fields = ["CandidateID", "CandidateFullName"]
    for field in critical_fields:
        if any(field in m for m in found_fields):
            print(f"✅ {field} FOUND in manifest!")
        else:
            print(f"❌ {field} MISSING from manifest!")

if __name__ == "__main__":
    asyncio.run(test_e2e_analysis())
