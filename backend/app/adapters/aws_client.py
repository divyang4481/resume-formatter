from __future__ import annotations

from typing import Any

import boto3

from app.config import settings


def aws_service_client(service_name: str, **kwargs: Any):
    """Create a boto3 client, routing only S3/SQS to LocalStack when configured."""
    client_kwargs: dict[str, Any] = dict(kwargs)
    client_kwargs.setdefault("region_name", settings.aws_region)

    if service_name in {"s3", "sqs"} and settings.aws_endpoint_url:
        client_kwargs["endpoint_url"] = settings.aws_endpoint_url
        client_kwargs.setdefault("aws_access_key_id", settings.localstack_aws_access_key_id)
        client_kwargs.setdefault("aws_secret_access_key", settings.localstack_aws_secret_access_key)

    return boto3.client(service_name, **client_kwargs)
