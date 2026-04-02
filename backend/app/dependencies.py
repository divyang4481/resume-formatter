from typing import Optional
from app.config import settings
from app.adapters.base import LlmRuntimeAdapter
from app.domain.interfaces import StorageProvider, TemplateRepository, EventBus, DocumentExtractionService

def get_document_extraction_service() -> DocumentExtractionService:
    """
    Dependency Factory to fetch the document extraction service.
    Now uses the multi-tier ParserRouter internally.
    """
    from app.services.extraction_service_adapter import RouterBasedExtractionService
    return RouterBasedExtractionService()

def get_llm_runtime() -> LlmRuntimeAdapter:
    """
    Dependency Factory to fetch the configured LLM runtime adapter.
    Resolves to AWS Bedrock, Azure OpenAI, GCP Vertex AI, Local Ollama, or Gemini.
    """
    backend = settings.llm_backend.lower()
    
    # Check if local overrides
    if backend == "local_ollama" or (settings.cloud.lower() == "local" and backend not in ["gemini"]):
        from app.adapters.impls.local.llm_runtime import LocalOllamaLlmRuntime
        return LocalOllamaLlmRuntime(
            model_name=settings.llm_model_name,
            endpoint=settings.ollama_endpoint
        )
    elif backend == "gemini":
        from app.adapters.impls.local.gemini_runtime import GeminiLlmRuntime
        return GeminiLlmRuntime(
            api_key=settings.gemini_api_key,
            model_name=settings.llm_model_name if settings.llm_model_name != "llama3" else "gemini-2.0-flash"
        )

    if backend == "aws_bedrock":
        from app.adapters.impls.aws.llm_runtime import AwsBedrockLlmRuntime
        return AwsBedrockLlmRuntime(
            model_id=settings.llm_model_name,
            region_name=settings.aws_region
        )
    elif backend == "gcp_vertex":
        from app.adapters.impls.gcp.llm_runtime import GcpVertexLlmRuntime
        return GcpVertexLlmRuntime(
            project_id=settings.gcp_project_id,
            location=settings.gcp_location,
            model_name=settings.llm_model_name
        )
    elif backend == "azure_openai":
        from app.adapters.impls.azure.llm_runtime import AzureOpenAiLlmRuntime
        return AzureOpenAiLlmRuntime(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment_name=settings.azure_openai_deployment_name,
            api_version=settings.azure_openai_api_version
        )
    else:
        # Fallback to local
        from app.adapters.impls.local.llm_runtime import LocalOllamaLlmRuntime
        return LocalOllamaLlmRuntime(
            model_name=settings.llm_model_name,
            endpoint=settings.ollama_endpoint
        )

def get_storage_provider() -> StorageProvider:
    """
    Dependency Factory to fetch the configured storage provider adapter.
    Resolves to Local, S3, GCP, or Azure based on configuration.
    """
    backend = settings.storage_backend.lower()

    if backend == "s3":
        from app.adapters.storage.s3_storage import S3StorageProvider
        return S3StorageProvider(bucket=settings.s3_bucket, region=settings.aws_region)
    elif backend == "gcp":
        from app.adapters.storage.gcp_storage import GcpCloudStorageProvider
        # You'd normally add a setting for GCP bucket, reusing s3_bucket as generic bucket for now or hardcoding
        return GcpCloudStorageProvider(bucket=settings.s3_bucket, project_id=settings.gcp_project_id)
    elif backend == "azure":
        from app.adapters.storage.azure_storage import AzureBlobStorageProvider
        return AzureBlobStorageProvider(container=settings.s3_bucket)
    elif backend == "local":
        from app.adapters.storage.local_storage import LocalStorageProvider
        return LocalStorageProvider(base_path=settings.local_storage_path)
    else:
        # Fallback to local
        from app.adapters.storage.local_storage import LocalStorageProvider
        return LocalStorageProvider(base_path=settings.local_storage_path)


from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

def get_db_session():
    """Dependency to get SQLAlchemy DB Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def mock_is_admin(x_admin_token: Optional[str] = Header(None, description="Mock admin token for RBAC")) -> bool:
    """
    Mock dependency to simulate RBAC for admin endpoints.
    Requires a valid X-Admin-Token header.
    """
    if x_admin_token != "admin-secret-token":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin access required"
        )
    return True

# Fast API dependency injection wrappers
def document_extraction_service_dependency() -> DocumentExtractionService:
    return get_document_extraction_service()

def llm_runtime_dependency() -> LlmRuntimeAdapter:
    return get_llm_runtime()


from app.domain.interfaces import StorageProvider, JobRepository
from app.adapters.storage.local_storage import LocalStorageProvider



from app.domain.interfaces import KnowledgeIndex

def get_knowledge_index() -> KnowledgeIndex:
    """
    Dependency Factory to fetch the Knowledge Index.
    Attempts Qdrant -> Chroma -> InMemory.
    """
    try:
        from app.adapters.vector.qdrant_index import QdrantKnowledgeIndex
        return QdrantKnowledgeIndex()
    except Exception as e:
        print(f"Failed to load Qdrant, falling back to Chroma: {e}")
        try:
            from app.adapters.vector.chroma_index import ChromaKnowledgeIndex
            return ChromaKnowledgeIndex()
        except Exception as e2:
            print(f"Failed to load Chroma, falling back to InMemory: {e2}")
            from app.adapters.vector.in_memory_index import InMemoryKnowledgeIndex
            return InMemoryKnowledgeIndex()

def get_template_repository(db: Session = Depends(get_db_session)) -> TemplateRepository:
    """Dependency Factory to fetch Template Repository"""
    from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
    return SqlAlchemyTemplateRepository(db=db)

def template_repository_dependency(repo: TemplateRepository = Depends(get_template_repository)) -> TemplateRepository:
    return repo

def get_knowledge_repository(db: Session = Depends(get_db_session)):
    """Dependency Factory to fetch Knowledge Repository (Stubbed)"""
    # A real implementation would go here similar to SqlAlchemyTemplateRepository
    pass

def get_job_repository(db: Session = Depends(get_db_session)) -> JobRepository:
    """Dependency Factory to fetch Job Repository"""
    from app.adapters.repositories.job_repository import SqlAlchemyJobRepository
    return SqlAlchemyJobRepository(db=db)

def job_repository_dependency(repo: JobRepository = Depends(get_job_repository)) -> JobRepository:
    return repo

def get_validation_repository(db: Session = Depends(get_db_session)):
    """Dependency Factory to fetch Validation Repository (Stubbed)"""
    pass

def storage_provider_dependency() -> StorageProvider:
    return get_storage_provider()

from app.domain.interfaces import MessageQueue
def get_message_queue(db: Session = Depends(get_db_session)) -> MessageQueue:
    from app.adapters.impls.local.local_queue import SqlAlchemyMessageQueue
    return SqlAlchemyMessageQueue(db=db)

def message_queue_dependency(queue: MessageQueue = Depends(get_message_queue)) -> MessageQueue:
    return queue


_local_event_bus = None
def get_event_bus() -> EventBus:
    global _local_event_bus
    if _local_event_bus is None:
        from app.adapters.impls.local.event_bus import LocalEventBus
        _local_event_bus = LocalEventBus()
    return _local_event_bus

def event_bus_dependency() -> EventBus:
    return get_event_bus()
