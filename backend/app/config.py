from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application Settings configured via environment variables.
    """

    project_name: str = "Agentic Document Platform"

    # Architecture Config
    cloud_provider: str = "aws"  # "aws", "local"
    runtime_mode: str = "local"  # "local" or "aws"
    processing_mode: str = "async"  # "sync" or "async"
    queue_provider: str = "local"  # "local", "sqs"
    storage_provider: str = "local"  # "local", "s3"
    knowledge_provider: str = "local"  # "local", "bedrock_kb"
    agent_provider: str = "python_orchestrated"  # "python_orchestrated", "bedrock_agent"
    document_parser_provider: str = "docling_service"  # "docling_service", "local_docling", "cloud_ai"
    parser_service_url: str = "http://parser-docling:8080"

    # AWS Specific Config
    aws_region: str = "ap-south-1"
    s3_bucket_input: str = "agentic-document-input-bucket"
    s3_bucket_output: str = "agentic-document-output-bucket"
    sqs_processing_queue_url: str = ""
    bedrock_agent_id: str = ""
    bedrock_agent_alias_id: str = ""
    bedrock_kb_id: str = ""
    database_url: str = "sqlite:///./.data/app.db"
    aws_bearer_token_bedrock: str = ""
    aws_endpoint_url: str = ""
    localstack_aws_access_key_id: str = "test"
    localstack_aws_secret_access_key: str = "test"

    # Document Parsing Routing & Guard
    enable_docling: bool = True
    enable_gpu_worker: bool = False
    parser_timeout_seconds: int = 300
    max_file_size_mb: int = 10

    # Document Parsing Routing & Thresholds
    document_parser_primary_pdf: str = "docling"
    document_parser_primary_docx: str = "docling"

    # Thresholds for parsing confidence & routing
    parser_min_text_chars: int = 300
    parser_min_section_count: int = 3
    parser_min_confidence: float = 0.65

    # LLM Settings — default / global
    llm_backend: str = "aws_bedrock"
    llm_model_name: str = "qwen.qwen3-235b-a22b-2507-v1:0"
    ollama_endpoint: str = "http://localhost:11434/api/generate"

    # ---------------------------------------------------------------------------
    # Bedrock per-task model routing
    # ---------------------------------------------------------------------------
    # Primary model for tasks requiring precise structured JSON output
    bedrock_default_model_id: str = "qwen.qwen3-235b-a22b-2507-v1:0"

    # Template analysis uses Claude Sonnet for superior instruction-following
    # and deterministic JSON generation. Set to empty string to fall back to default.
    bedrock_template_analysis_model_id: str = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"

    # Resume summary generation — Qwen is fine for narrative tasks
    bedrock_resume_summary_model_id: str = ""  # falls back to default

    # Data mapping (resume fields → template contract)
    bedrock_data_mapping_model_id: str = ""  # falls back to default

    # Fallback model if primary model fails (access error / throttle exhaust)
    bedrock_fallback_model_id: str = "qwen.qwen3-235b-a22b-2507-v1:0"

    # Template analysis quality controls
    bedrock_max_output_tokens_template_analysis: int = 8192
    bedrock_temperature_template_analysis: float = 0.0   # Deterministic JSON

    # General output token limits
    bedrock_max_output_tokens_default: int = 4096
    bedrock_temperature_default: float = 0.1
    # ---------------------------------------------------------------------------

    # New Model-Routed Pipeline Config
    template_analysis_model_profile: str = "balanced"
    template_analysis_models: dict = {
        "evidence_normalizer": {
            "provider": "aws_bedrock",
            "model_id": "amazon.nova-lite-v1:0",
            "temperature": 0.0,
            "max_tokens": 4000
        },
        "manifest_generator": {
            "provider": "aws_bedrock",
            "model_id": "qwen.qwen3-235b-a22b-2507-v1:0",
            "temperature": 0.0,
            "max_tokens": 12000
        },
        "manifest_repair": {
            "provider": "aws_bedrock",
            "model_id": "qwen.qwen3-235b-a22b-2507-v1:0",
            "temperature": 0.0,
            "max_tokens": 12000
        },
        "manifest_critic": {
            "provider": "aws_bedrock",
            "model_id": "apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "temperature": 0.0,
            "max_tokens": 6000,
            "enabled": False
        }
    }

    # Storage Settings
    local_storage_path: str = "./data"

    # Vector search and shadow mode feature flags
    vector_search_enabled: bool = False
    template_selector_mode: str = "legacy"

    # Example standard settings
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

