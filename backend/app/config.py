from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Application Settings configured via environment variables.
    """
    project_name: str = "Agentic Document Platform"

    # Cloud and Adapter Selection
    cloud: str = "local"  # "aws", "azure", "gcp", "ibm", "local"
    document_parser_backend: str = "local_parser"
    document_parser_fallback: str = "tika"
    ocr_backend: str = "local"
    docx_parser_backend: str = "local"
    enable_multi_backend_routing: bool = False

    # LLM Settings
    llm_backend: str = "local_ollama" # "aws_bedrock", "gcp_vertex", "azure_openai", "local_ollama"
    llm_model_name: str = "llama3" # Default Ollama model. Override with Claude/Gemini/GPT for cloud.

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

    # Example standard settings
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
