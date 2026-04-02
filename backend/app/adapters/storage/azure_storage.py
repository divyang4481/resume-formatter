from app.domain.interfaces import StorageProvider


class AzureBlobStorageProvider(StorageProvider):
    def __init__(self, container: str, account_name: str = ""):
        """
        Stub for an Azure Blob Storage provider.
        This would typically initialize an azure-storage-blob client.
        """
        self.container = container
        self.account_name = account_name

    def put_bytes(self, key: str, data: bytes) -> str:
        # Stub: Put object directly in container
        return self.build_uri(key)

    def put_file(self, key: str, file_path: str) -> str:
        # Stub: Upload local file to Azure Blob
        return self.build_uri(key)

    def get_bytes(self, key: str) -> bytes:
        # Stub: Fetch object from Azure Blob and return content bytes
        return b""

    def get_to_path(self, key: str, file_path: str) -> None:
        # Stub: Download object from Azure Blob to local path
        pass

    def exists(self, key: str) -> bool:
        # Stub: Head object check
        return False

    def delete(self, key: str) -> bool:
        # Stub: Delete object in container
        return True

    def build_uri(self, key: str) -> str:
        # Uses Azure Blob URL format
        return f"https://{self.account_name}.blob.core.windows.net/{self.container}/{key}"
