from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application Settings configured via environment variables.
    """

    project_name: str = "Agentic Document Platform"

    # Cloud and Adapter Selection
    cloud: str = "local"  # "aws", "azure", "gcp", "ibm", "local"

    # Document Parsing Routing & Thresholds
    document_parser_primary_pdf: str = "docling"
    document_parser_fallback_pdf: str = "tika"
    document_parser_primary_docx: str = "docling"
    document_parser_fallback_docx: str = "tika"

    # Thresholds for parsing confidence & routing
    parser_min_text_chars: int = 300
    parser_min_section_count: int = 3
    parser_min_confidence: float = 0.65
    parser_timeout_seconds: int = 45

    # LLM Settings
    llm_backend: str = (
        "local_ollama"  # "aws_bedrock", "gcp_vertex", "azure_openai", "local_ollama", "gemini"
    )
    llm_model_name: str = (
        "llama3:latest"  # Default Ollama model. Override with Claude/Gemini/GPT for cloud.
    )
    ollama_endpoint: str = (
        "http://localhost:11434/api/generate"  # Default for local Ollama
    )
    gemini_api_key: str = (
        ""  # Key for Google Gemini API
    )

    # AWS Settings
    aws_region: str = "us-east-1"

    # GCP Settings
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"

    # Azure Settings
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_name: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"

    # Storage Settings
    storage_backend: str = "local"  # "local", "s3"
    local_storage_path: str = "./data"
    s3_bucket: str = "agentic-document-platform-bucket"

    # Vector search and shadow mode feature flags
    vector_search_enabled: bool = False
    template_selector_mode: str = "legacy"  # "legacy", "shadow", "hybrid"

    # Audit Logging
    enable_audit_logging: bool = True

    # Example standard settings
    log_level: str = "INFO"

    # Worker and Asynchronous Settings
    max_parallel_jobs: int = 3
    message_queue_poll_interval: int = 2

    class Config:
        env_file = ".env"


settings = Settings()
