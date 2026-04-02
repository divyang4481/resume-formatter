from typing import Optional
from app.config import settings
from app.adapters.base import DocumentParserAdapter, LlmRuntimeAdapter
from app.domain.interfaces import StorageProvider, TemplateRepository, EventBus

def get_document_parser() -> DocumentParserAdapter:
    """
    Dependency Factory to fetch the configured document parsing adapter.
    This logic dynamically resolves implementations based on the system config.
    """
    backend = settings.document_parser_backend.lower()

    if backend == "azure_document_intelligence":
        from app.adapters.impls.azure.document_parser import AzureDocumentIntelligenceParser
        return AzureDocumentIntelligenceParser()
    elif backend == "aws_textract":
        from app.adapters.impls.aws.document_parser import AwsTextractParser
        return AwsTextractParser()
    elif backend == "gcp_document_ai":
        from app.adapters.impls.gcp.document_parser import GcpDocumentAiParser
        return GcpDocumentAiParser()
    elif backend == "ibm_docling":
        from app.adapters.impls.ibm.document_parser import IbmDoclingParser
        return IbmDoclingParser()
    elif backend == "tika":
        from app.adapters.impls.local.document_parser import ApacheTikaParser
        return ApacheTikaParser()
    elif backend == "local_parser":
        from app.adapters.impls.local.document_parser import LocalParser
        return LocalParser()
    else:
        # Fallback to local parser
        from app.adapters.impls.local.document_parser import LocalParser
        return LocalParser()

def get_llm_runtime() -> LlmRuntimeAdapter:
    """
    Dependency Factory to fetch the configured LLM runtime adapter.
    Resolves to AWS Bedrock, Azure OpenAI, GCP Vertex AI, or Local Ollama.
    """
    backend = settings.llm_backend.lower()

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
    elif backend == "local_ollama":
        from app.adapters.impls.local.llm_runtime import LocalOllamaLlmRuntime
        return LocalOllamaLlmRuntime(
            model_name=settings.llm_model_name
        )
    else:
        # Fallback to local
        from app.adapters.impls.local.llm_runtime import LocalOllamaLlmRuntime
        return LocalOllamaLlmRuntime(
            model_name="llama3"
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


from fastapi import Header, HTTPException, status

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
def document_parser_dependency() -> DocumentParserAdapter:
    return get_document_parser()

def llm_runtime_dependency() -> LlmRuntimeAdapter:
    return get_llm_runtime()


from app.domain.interfaces import StorageProvider, JobRepository
from app.adapters.storage.local_storage import LocalStorageProvider

def get_storage_provider() -> StorageProvider:
    # Factory to get storage provider. Defaulting to local storage for now.
    return LocalStorageProvider(base_path=settings.data_dir if hasattr(settings, 'data_dir') else "./data")

def storage_provider_dependency() -> StorageProvider:
    return get_storage_provider()


from app.adapters.impls.local.job_repository import InMemoryJobRepository

_job_repo_instance = InMemoryJobRepository()

def get_job_repository() -> JobRepository:
    return _job_repo_instance

def job_repository_dependency() -> JobRepository:
    return get_job_repository()
def storage_provider_dependency() -> StorageProvider:
    return get_storage_provider()

def get_template_repository() -> TemplateRepository:
    """
    Dependency Factory to fetch the configured Template Repository.
    Currently defaults to an in-memory implementation for Story 2.2.
    """
    from app.adapters.impls.local.template_repository import InMemoryTemplateRepository
    # Typically would be singleton or injected correctly, but initializing per request for now
    # Since this is in-memory, to persist across requests it should be instantiated globally
    pass

_in_memory_template_repo = None
def get_global_template_repository() -> TemplateRepository:
    global _in_memory_template_repo
    if _in_memory_template_repo is None:
        from app.adapters.impls.local.template_repository import InMemoryTemplateRepository
        _in_memory_template_repo = InMemoryTemplateRepository()
    return _in_memory_template_repo

def template_repository_dependency() -> TemplateRepository:
    return get_global_template_repository()

_local_event_bus = None
def get_event_bus() -> EventBus:
    global _local_event_bus
    if _local_event_bus is None:
        from app.adapters.impls.local.event_bus import LocalEventBus
        _local_event_bus = LocalEventBus()
    return _local_event_bus

def event_bus_dependency() -> EventBus:
    return get_event_bus()
