import os
from typing import Any

from app.adapters.storage.s3_object_storage import LocalObjectStorage, S3ObjectStorage
from app.config import settings


def get_parser_storage() -> Any:
    if settings.storage_provider == "s3":
        return S3ObjectStorage()
    return LocalObjectStorage()


def put_json_bytes(storage: Any, output_uri: str, data: bytes) -> str:
    """Write parser output to an explicit URI without leaking this logic into workers."""
    if output_uri.startswith("file://"):
        target = output_uri.replace("file://", "", 1)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
        return output_uri

    if output_uri.startswith("s3://"):
        bucket_and_key = output_uri.replace("s3://", "", 1).split("/", 1)
        bucket = bucket_and_key[0]
        key = bucket_and_key[1]
        return S3ObjectStorage(bucket_name=bucket).put_bytes(data, key, "application/json")

    return storage.put_bytes(data, output_uri, "application/json")
