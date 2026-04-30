from typing import Any, Dict, Optional
import json
import boto3

from app.domain.interfaces import MessageQueue
from app.config import settings


class SqsMessageQueue(MessageQueue):
    def __init__(self, queue_url: str, region_name: str):
        self.queue_url = queue_url
        self._client = boto3.client("sqs", region_name=region_name)

    def enqueue(self, queue_name: str, payload: Dict[str, Any]) -> None:
        self._client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(payload)
        )

    def dequeue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        response = self._client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
            VisibilityTimeout=settings.message_queue_visibility_timeout_seconds
        )
        messages = response.get("Messages", [])
        if not messages:
            return None

        msg = messages[0]
        payload = json.loads(msg["Body"])
        payload["_queue_receipt_handle"] = msg["ReceiptHandle"]
        return payload

    def mark_completed(self, queue_name: str, message: Dict[str, Any]) -> None:
        receipt_handle = message.get("_queue_receipt_handle")
        if not receipt_handle:
            return
        self._client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle
        )

    def mark_failed(self, queue_name: str, message: Dict[str, Any], error: Optional[str] = None) -> None:
        receipt_handle = message.get("_queue_receipt_handle")
        if not receipt_handle:
            return
        # Make message visible quickly for retry; DLQ policy can be managed in AWS.
        self._client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=0
        )
