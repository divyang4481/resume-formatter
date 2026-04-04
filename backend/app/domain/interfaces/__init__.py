from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


from .document_extraction import DocumentExtractionService, ExtractionContext, ExtractedDocument
from .embedding import EmbeddingProvider
from .llm import LlmRuntimeAdapter
from .privacy import PiiDetectorAdapter

class TemplateRepository(ABC):
    @abstractmethod
    def get_template(self, template_id: str, version: Optional[str] = None) -> Any:
        """Fetches a template asset."""
        pass

    @abstractmethod
    def save_template(self, template_asset: Any) -> str:
        """Saves a template asset."""
        pass

    @abstractmethod
    def list_templates(self, filters: Dict[str, Any]) -> List[Any]:
        """Lists templates according to filters."""
        pass


class KnowledgeIndex(ABC):
    @abstractmethod
    def index_chunks(self, chunks: List[Dict[str, Any]], asset_id: str) -> None:
        """Stores knowledge chunks into the index."""
        pass

    @abstractmethod
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches the index."""
        pass


class Renderer(ABC):
    @abstractmethod
    def render_docx(self, template_ref: str, payload: Dict[str, Any]) -> bytes:
        """Renders payload into a DOCX template."""
        pass

    @abstractmethod
    def render_pdf(self, template_ref: str, payload: Dict[str, Any]) -> bytes:
        """Renders payload into a PDF template."""
        pass


class StorageProvider(ABC):
    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> str:
        """Stores bytes and returns reference."""
        pass

    @abstractmethod
    def put_file(self, key: str, file_path: str) -> str:
        """Stores local file and returns reference."""
        pass

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Retrieves object as bytes."""
        pass

    @abstractmethod
    def get_to_path(self, key: str, file_path: str) -> None:
        """Downloads object to a local path."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Checks if object exists."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Deletes object."""
        pass

    @abstractmethod
    def build_uri(self, key: str) -> str:
        """Returns provider-specific URI for an object key."""
        pass


class JobRepository(ABC):
    @abstractmethod
    def get_job(self, job_id: str) -> Any:
        """Fetches a processing job."""
        pass

    @abstractmethod
    def save_job(self, job: Any) -> str:
        """Saves a processing job."""
        pass


class MessageQueue(ABC):
    @abstractmethod
    def enqueue(self, queue_name: str, payload: Dict[str, Any]) -> None:
        """Enqueues a message."""
        pass

    @abstractmethod
    def dequeue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Dequeues a message (if available)."""
        pass

class EventBus(ABC):
    @abstractmethod
    def publish(self, topic: str, event: Any) -> None:
        """Publishes an event to a specific topic."""
        pass

    @abstractmethod
    def audit(self, action: str, details: Dict[str, Any]) -> None:
        """Records an action for auditing purposes."""
        pass

