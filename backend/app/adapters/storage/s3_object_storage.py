import boto3
import os
import uuid
import logging
from app.domain.interfaces.storage import ObjectStorage
from app.config import settings

logger = logging.getLogger(__name__)

class S3ObjectStorage(ObjectStorage):
    def __init__(self, bucket_name: str = None):
        self.bucket = bucket_name or settings.s3_bucket_output
        self.s3 = boto3.client('s3', region_name=settings.aws_region)

    def put_file(self, local_path: str, key: str, content_type: str = "application/octet-stream") -> str:
        try:
            self.s3.upload_file(
                local_path,
                self.bucket,
                key,
                ExtraArgs={'ContentType': content_type}
            )
            return f"s3://{self.bucket}/{key}"
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    def get_file(self, uri: str, target_path: str) -> str:
        try:
            if not uri.startswith("s3://"):
                raise ValueError(f"Invalid S3 URI: {uri}")

            parts = uri.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]

            self.s3.download_file(bucket, key, target_path)
            return target_path
        except Exception as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise

    def put_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type
            )
            return f"s3://{self.bucket}/{key}"
        except Exception as e:
            logger.error(f"Failed to upload bytes to S3: {e}")
            raise

    def presign_get_url(self, uri: str, expires_seconds: int = 3600) -> str:
        try:
            if not uri.startswith("s3://"):
                return uri

            parts = uri.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]

            url = self.s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expires_seconds
            )
            return url
        except Exception as e:
            logger.error(f"Failed to presign S3 url: {e}")
            return ""

    def exists(self, uri: str) -> bool:
        try:
            if not uri.startswith("s3://"):
                return False

            parts = uri.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]
            self.s3.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def get_bytes(self, uri: str) -> bytes:
        try:
            if not uri.startswith("s3://"):
                raise ValueError(f"Invalid S3 URI: {uri}")
            parts = uri.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]
            response = self.s3.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Failed to get bytes from S3: {e}")
            raise


class LocalObjectStorage(ObjectStorage):
    def __init__(self, base_path: str = None):
        self.base_path = base_path or settings.local_storage_path
        os.makedirs(self.base_path, exist_ok=True)

    def put_file(self, local_path: str, key: str, content_type: str = "") -> str:
        import shutil
        target_path = os.path.join(self.base_path, key)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(local_path, target_path)
        return f"file://{target_path}"

    def get_file(self, uri: str, target_path: str) -> str:
        import shutil
        source_path = uri.replace("file://", "")
        shutil.copy2(source_path, target_path)
        return target_path

    def put_bytes(self, data: bytes, key: str, content_type: str = "") -> str:
        target_path = os.path.join(self.base_path, key)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'wb') as f:
            f.write(data)
        return f"file://{target_path}"

    def presign_get_url(self, uri: str, expires_seconds: int = 3600) -> str:
        return uri

    def exists(self, uri: str) -> bool:
        path = uri.replace("file://", "")
        return os.path.exists(path)

    def get_bytes(self, uri: str) -> bytes:
        path = uri.replace("file://", "")
        with open(path, 'rb') as f:
            return f.read()
