from typing import Optional
from app.config import settings
from app.adapters.base import DocumentParserAdapter, LlmRuntimeAdapter

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
