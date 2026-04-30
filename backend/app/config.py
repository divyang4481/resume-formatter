from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Application Settings configured via environment variables.
    """
    project_name: str = "Agentic Document Platform"

    # Architecture Config
    cloud_provider: str = "aws"  # "aws", "azure", "gcp", "local"
    runtime_mode: str = "local" # "local" or "aws"
    processing_mode: str = "async" # "sync" or "async"
    queue_provider: str = "local" # "local", "sqs"
    storage_provider: str = "local" # "local", "s3"
    knowledge_provider: str = "local" # "local", "bedrock_kb"
    agent_provider: str = "local_llm" # "local_llm", "bedrock_agent"

    # AWS Specific Config
    aws_region: str = "us-east-1"
    s3_bucket_input: str = "agentic-document-input-bucket"
    s3_bucket_output: str = "agentic-document-output-bucket"
    sqs_processing_queue_url: str = ""
    bedrock_agent_id: str = ""
    bedrock_agent_alias_id: str = ""
    bedrock_kb_id: str = ""

    # Document Parsing Routing & Guard
    enable_docling: bool = True
    enable_tika_fallback: bool = True
    enable_gpu_worker: bool = False
    parser_timeout_seconds: int = 300
    max_file_size_mb: int = 10

    # Legacy Document Parsing Routing & Thresholds (Keep for fallback)
    document_parser_primary_pdf: str = "docling"
    document_parser_fallback_pdf: str = "tika"
    document_parser_primary_docx: str = "docling"
    document_parser_fallback_docx: str = "tika"

    # Thresholds for parsing confidence & routing
    parser_min_text_chars: int = 300
    parser_min_section_count: int = 3
    parser_min_confidence: float = 0.65

    # LLM Settings
    llm_backend: str = "aws_bedrock"
    llm_model_name: str = "meta.llama3-8b-instruct-v1:0"
    ollama_endpoint: str = "http://localhost:11434/api/generate"
    gemini_api_key: str = ""

    # Storage Settings
    local_storage_path: str = "./data"

    # Vector search and shadow mode feature flags
    vector_search_enabled: bool = False
    template_selector_mode: str = "legacy"

    # Example standard settings
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

settings = Settings()
