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

    # Example standard settings
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
