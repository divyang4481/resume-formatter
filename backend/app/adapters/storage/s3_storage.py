import logging
from typing import Tuple
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from app.domain.interfaces import StorageProvider

logger = logging.getLogger(__name__)


class S3StorageProvider(StorageProvider):
    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def _resolve_bucket_key(self, ref: str) -> Tuple[str, str]:
        """Accept either raw key (jobs/...) or full s3://bucket/key URI."""
        if ref.startswith("s3://"):
            parsed = urlparse(ref)
            bucket = parsed.netloc or self.bucket
            key = parsed.path.lstrip("/")
            return bucket, key
        return self.bucket, ref.lstrip("/")

    def put_bytes(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        logger.info(f"S3: uploaded {len(data)} bytes to s3://{self.bucket}/{key}")
        return self.build_uri(key)

    def put_file(self, key: str, file_path: str) -> str:
        self.client.upload_file(file_path, self.bucket, key)
        logger.info(f"S3: uploaded file {file_path} to s3://{self.bucket}/{key}")
        return self.build_uri(key)

    def get_bytes(self, key: str) -> bytes:
        bucket, resolved_key = self._resolve_bucket_key(key)
        response = self.client.get_object(Bucket=bucket, Key=resolved_key)
        data = response["Body"].read()
        logger.info(f"S3: downloaded {len(data)} bytes from s3://{bucket}/{resolved_key}")
        return data

    def get_to_path(self, key: str, file_path: str) -> None:
        bucket, resolved_key = self._resolve_bucket_key(key)
        self.client.download_file(bucket, resolved_key, file_path)
        logger.info(f"S3: downloaded s3://{bucket}/{resolved_key} to {file_path}")

    def exists(self, key: str) -> bool:
        bucket, resolved_key = self._resolve_bucket_key(key)
        try:
            self.client.head_object(Bucket=bucket, Key=resolved_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def delete(self, key: str) -> bool:
        bucket, resolved_key = self._resolve_bucket_key(key)
        try:
            self.client.delete_object(Bucket=bucket, Key=resolved_key)
            return True
        except ClientError as e:
            logger.error(f"S3: failed to delete s3://{bucket}/{resolved_key}: {e}")
            return False

    def build_uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"
