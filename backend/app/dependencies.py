from typing import Optional
from app.config import settings
from app.adapters.base import DocumentParserAdapter

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

# Fast API dependency injection wrapper
def document_parser_dependency() -> DocumentParserAdapter:
    return get_document_parser()
