import re

def update_admin_analyze():
    with open('backend/app/api/admin.py', 'r') as f:
        content = f.read()

    old_analyze_body = """        from app.services.resume_ai_service import ResumeAiService
        ai_service = ResumeAiService(llm, extraction_service)
        analyzer = TemplateAnalysisService(ai_service=ai_service)
        suggestions = await analyzer.analyze_template(template_bytes, template.file_name or "template.docx")"""

    new_analyze_body = """        analyzer = TemplateAnalysisService(llm=llm, extraction_service=extraction_service)
        suggestions = await analyzer.analyze_template(template_bytes, template.file_name or "template.docx")"""

    if old_analyze_body in content:
        content = content.replace(old_analyze_body, new_analyze_body)
        with open('backend/app/api/admin.py', 'w') as f:
            f.write(content)
        print("Updated analyze_template in admin.py")
    else:
        print("Could not find analyze_template body in admin.py")

update_admin_analyze()
