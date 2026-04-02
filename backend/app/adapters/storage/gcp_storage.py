from app.domain.interfaces import StorageProvider


class GcpCloudStorageProvider(StorageProvider):
    def __init__(self, bucket: str, project_id: str = ""):
        """
        Stub for a Google Cloud Storage provider.
        This would typically initialize a google-cloud-storage client.
        """
        self.bucket = bucket
        self.project_id = project_id

    def put_bytes(self, key: str, data: bytes) -> str:
        # Stub: Put object directly in bucket
        return self.build_uri(key)

    def put_file(self, key: str, file_path: str) -> str:
        # Stub: Upload local file to GCS
        return self.build_uri(key)

    def get_bytes(self, key: str) -> bytes:
        # Stub: Fetch object from GCS and return content bytes
        return b""

    def get_to_path(self, key: str, file_path: str) -> None:
        # Stub: Download object from GCS to local path
        pass

    def exists(self, key: str) -> bool:
        # Stub: Head object check
        return False

    def delete(self, key: str) -> bool:
        # Stub: Delete object in bucket
        return True

    def build_uri(self, key: str) -> str:
        # Uses GCS URI format
        return f"gs://{self.bucket}/{key}"
