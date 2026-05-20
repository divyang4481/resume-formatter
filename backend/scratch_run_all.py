import asyncio
import os
import sys
import logging

# Configure logging to see bedrock interaction details
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from app.services.template_analysis_service import TemplateAnalysisService

async def main():
    service = TemplateAnalysisService()
    templates = [
        "../SampleData/templates/UK Taxation.docx",
        "../SampleData/templates/UK Telecoms.docx",
        "../SampleData/templates/UK Treasury.docx",
        "../SampleData/templates/UK Worldwide London.docx",
    ]
    for path in templates:
        print(f"\n==================================================")
        print(f"Analyzing {path}...")
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue
            
        with open(path, "rb") as f:
            content = f.read()
        
        try:
            analysis = await service.analyze_template(content, os.path.basename(path))
            print(f"Analysis Status: {analysis.analysis_status}")
            fields = analysis.fields
            print("Detected fields:")
            skills_field = None
            for field in fields:
                print(f"  - {field.fieldname} ({field.field_type}): marker={repr(field.marker_text)}")
                if field.fieldname == "skills":
                    skills_field = field
            
            if skills_field:
                print(f"SUCCESS: 'skills' field found!")
                print(f"  Fieldname: {skills_field.fieldname}")
                print(f"  Field type: {skills_field.field_type}")
                print(f"  Marker: {repr(skills_field.marker_text)}")
                print(f"  Locator strategy: {skills_field.render_locator.strategy}")
                print(f"  Locator details: {skills_field.render_locator}")
            else:
                print(f"FAILED: 'skills' field NOT found in manifest fields!")
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
