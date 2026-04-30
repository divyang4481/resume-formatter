from abc import ABC, abstractmethod

class ObjectStorage(ABC):
    @abstractmethod
    def put_file(self, local_path: str, key: str, content_type: str) -> str:
        """Stores a local file."""
        pass

    @abstractmethod
    def get_file(self, uri: str, target_path: str) -> str:
        """Downloads a file to a local path."""
        pass

    @abstractmethod
    def put_bytes(self, data: bytes, key: str, content_type: str) -> str:
        """Stores bytes."""
        pass

    @abstractmethod
    def presign_get_url(self, uri: str, expires_seconds: int = 3600) -> str:
        """Generates a presigned URL."""
        pass

    @abstractmethod
    def exists(self, uri: str) -> bool:
        """Checks if an object exists."""
        pass
