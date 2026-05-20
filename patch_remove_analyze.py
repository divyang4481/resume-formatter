import re

def remove_analyze_from_ai_service():
    with open('backend/app/services/resume_ai_service.py', 'r') as f:
        content = f.read()

    # The analyze_template function is already copied to template_analysis_service.py
    # So we can remove it from resume_ai_service.py entirely.
    # It starts at "    async def analyze_template" and ends before "    async def validate_output"

    start_idx = content.find("    async def analyze_template")
    end_idx = content.find("    async def validate_output")

    if start_idx != -1 and end_idx != -1:
        content = content[:start_idx] + content[end_idx:]
        with open('backend/app/services/resume_ai_service.py', 'w') as f:
            f.write(content)
        print("Removed analyze_template from resume_ai_service.py")
    else:
        print("Could not find boundaries to remove analyze_template")

remove_analyze_from_ai_service()
