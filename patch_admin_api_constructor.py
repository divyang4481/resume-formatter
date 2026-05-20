def update_admin_api_constructor():
    with open('backend/app/api/admin.py', 'r') as f:
        content = f.read()

    # In upload_asset, we instantiated TemplateAnalysisService with ai_service instead of llm/extraction_service
    old_code = """        from app.services.resume_ai_service import ResumeAiService
        from app.services.template_analysis_service import TemplateAnalysisService
        ai_service = ResumeAiService(llm, extraction_service)

        template_service = TemplateService(
            storage_provider=storage_provider,
            template_repository=template_repository,
            event_bus=event_bus,
            extraction_service=extraction_service,
            knowledge_index=knowledge_index,
            template_analysis_service=TemplateAnalysisService(ai_service)
        )"""

    new_code = """        from app.services.template_analysis_service import TemplateAnalysisService

        template_service = TemplateService(
            storage_provider=storage_provider,
            template_repository=template_repository,
            event_bus=event_bus,
            extraction_service=extraction_service,
            knowledge_index=knowledge_index,
            template_analysis_service=TemplateAnalysisService(llm=llm, extraction_service=extraction_service)
        )"""

    if old_code in content:
        content = content.replace(old_code, new_code)
        with open('backend/app/api/admin.py', 'w') as f:
            f.write(content)
        print("Updated admin.py constructor for TemplateAnalysisService in upload_asset")
    else:
        print("Could not find upload_asset constructor code in admin.py")

update_admin_api_constructor()
