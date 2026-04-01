import os
import shutil
from pathlib import Path
from app.domain.interfaces import StorageProvider


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: str = "./data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_full_path(self, key: str) -> Path:
        """Helper to resolve the key into a local file path."""
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put_bytes(self, key: str, data: bytes) -> str:
        path = self._get_full_path(key)
        path.write_bytes(data)
        return self.build_uri(key)

    def put_file(self, key: str, file_path: str) -> str:
        target_path = self._get_full_path(key)
        shutil.copy2(file_path, target_path)
        return self.build_uri(key)

    def get_bytes(self, key: str) -> bytes:
        path = self._get_full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        return path.read_bytes()

    def get_to_path(self, key: str, file_path: str) -> None:
        src_path = self._get_full_path(key)
        if not src_path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, target_path)

    def exists(self, key: str) -> bool:
        return self._get_full_path(key).exists()

    def delete(self, key: str) -> bool:
        path = self._get_full_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def build_uri(self, key: str) -> str:
        return f"local://{key}"
