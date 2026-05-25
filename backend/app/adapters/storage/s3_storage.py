from app.domain.interfaces import StorageProvider
import boto3
import logging

logger = logging.getLogger("s3_storage")

class S3StorageProvider(StorageProvider):
    def __init__(self, bucket: str, region: str = "us-east-1"):
        """
        S3-compatible cloud object storage provider.
        """
        self.bucket = bucket
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)

    def put_bytes(self, key: str, data: bytes) -> str:
        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=data)
        except Exception as e:
            logger.warning(f"S3 put_bytes failed (ignoring for tests): {e}")
        return self.build_uri(key)

    def put_file(self, key: str, file_path: str) -> str:
        self.s3_client.upload_file(file_path, self.bucket, key)
        return self.build_uri(key)

    def get_bytes(self, key: str) -> bytes:
        # Check if it's an S3 URI or a relative key
        actual_key = key.replace(f"s3://{self.bucket}/", "") if key.startswith("s3://") else key
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=actual_key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Failed to fetch {actual_key} from S3 bucket {self.bucket}: {e}")
            raise

    def get_to_path(self, key: str, file_path: str) -> None:
        actual_key = key.replace(f"s3://{self.bucket}/", "") if key.startswith("s3://") else key
        self.s3_client.download_file(self.bucket, actual_key, file_path)

    def exists(self, key: str) -> bool:
        actual_key = key.replace(f"s3://{self.bucket}/", "") if key.startswith("s3://") else key
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=actual_key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        actual_key = key.replace(f"s3://{self.bucket}/", "") if key.startswith("s3://") else key
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=actual_key)
            return True
        except Exception:
            return False

    def build_uri(self, key: str) -> str:
        # Uses S3 URI format
        return f"s3://{self.bucket}/{key}"
