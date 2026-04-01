from app.domain.interfaces import StorageProvider


class S3StorageProvider(StorageProvider):
    def __init__(self, bucket: str, region: str = "us-east-1"):
        """
        Stub for an S3-compatible cloud object storage provider.
        This would typically initialize an AWS boto3 client or a minio client.
        """
        self.bucket = bucket
        self.region = region

    def put_bytes(self, key: str, data: bytes) -> str:
        # Stub: Put object directly in bucket
        return self.build_uri(key)

    def put_file(self, key: str, file_path: str) -> str:
        # Stub: Upload local file to S3
        return self.build_uri(key)

    def get_bytes(self, key: str) -> bytes:
        # Stub: Fetch object from S3 and return content bytes
        return b""

    def get_to_path(self, key: str, file_path: str) -> None:
        # Stub: Download object from S3 to local path
        pass

    def exists(self, key: str) -> bool:
        # Stub: Head object check
        return False

    def delete(self, key: str) -> bool:
        # Stub: Delete object in bucket
        return True

    def build_uri(self, key: str) -> str:
        # Uses S3 URI format
        return f"s3://{self.bucket}/{key}"
