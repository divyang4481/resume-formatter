import logging
from fastapi import Request
from typing import Optional

from app.db.session import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

# --- Mock RBAC ---
def mock_is_admin(request: Request) -> bool:
    """Mock dependency to ensure caller is admin."""
    return request.headers.get("X-Admin-Token") == "secret-admin-token"

# --- Database ---
def get_db_session():
    # Ensure tables exist (e.g. if they were dropped by clean_db.py while the server was running)
    try:
        from app.db.session import engine
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error(f"Error ensuring tables exist in get_db_session: {e}")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Adapters ---
def get_storage_provider():
    from app.adapters.storage.s3_object_storage import S3ObjectStorage, LocalObjectStorage
    if settings.storage_provider == "s3":
        return S3ObjectStorage()
    return LocalObjectStorage()

def get_message_queue():
    from app.adapters.queue.sqs_job_queue import SqsJobQueueAdapter, LocalJobQueueAdapter
    if settings.queue_provider == "sqs":
        return SqsJobQueueAdapter()
    return LocalJobQueueAdapter()

def get_document_extraction_service():
    from app.adapters.extraction.parser_router import ParserRouter
    return ParserRouter()

def get_llm_runtime():
    from app.adapters.llm.aws_bedrock_runtime import AwsBedrockLlmRuntime
    from app.adapters.llm.ollama_runtime import LocalOllamaLlmRuntime
    if settings.llm_backend == "aws_bedrock":
        return AwsBedrockLlmRuntime()
    return LocalOllamaLlmRuntime()

def get_agent_provider():
    from app.adapters.agent.bedrock_agent import BedrockResumeFormattingAgent
    from app.adapters.agent.python_agent import PythonOrchestratedResumeFormattingAgent
    if settings.agent_provider == "bedrock_agent":
        return BedrockResumeFormattingAgent()
    return PythonOrchestratedResumeFormattingAgent(llm=get_llm_runtime())

def get_knowledge_index():
    from app.adapters.knowledge_base_adapter import BedrockKnowledgeBaseAdapter, LocalKnowledgeBaseAdapter
    if settings.knowledge_provider == "bedrock_kb":
        return BedrockKnowledgeBaseAdapter()
    return LocalKnowledgeBaseAdapter()

# --- Repositories ---
from fastapi import Depends
def get_job_repository(db_session = Depends(get_db_session)):
    from app.adapters.repositories.job_repository import SqlAlchemyJobRepository
    return SqlAlchemyJobRepository(db_session)

def get_template_repository(db_session = Depends(get_db_session)):
    from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
    return SqlAlchemyTemplateRepository(db_session)

def get_template_lookup_service(template_repository = Depends(get_template_repository)):
    from app.services.template_lookup_service import TemplateLookupService
    return TemplateLookupService(template_repository)

# --- Services ---
def resume_workflow_service_dependency(llm, parser, job_repo, template_repo, storage):
    from app.services.resume_workflow_service import ResumeWorkflowService
    return ResumeWorkflowService(
        llm_runtime=llm,
        doc_parser=parser,
        job_repository=job_repo,
        template_repository=template_repo,
        storage_provider=storage
    )

def get_bedrock_analyzer():
    from app.adapters.llm.bedrock_template_analyzer import BedrockTemplateAnalyzer
    return BedrockTemplateAnalyzer()

def get_template_analysis_service():
    from app.services.template_analysis_service import TemplateAnalysisService
    return TemplateAnalysisService(analyzer=get_bedrock_analyzer())

def get_resume_fact_extraction_service():
    from app.services.resume_fact_extraction_service import ResumeFactExtractionService
    return ResumeFactExtractionService(analyzer=get_bedrock_analyzer())

def get_template_field_mapper():
    from app.services.template_field_mapper import TemplateFieldMapper
    return TemplateFieldMapper(analyzer=get_bedrock_analyzer())

def get_docx_template_renderer():
    from app.services.docx_template_renderer import DocxTemplateRenderer
    return DocxTemplateRenderer()
