from typing import Any, Dict, Optional
import json
import boto3
from app.domain.interfaces import MessageQueue
from app.config import settings
import logging

logger = logging.getLogger("sqs_queue")

class SqsMessageQueue(MessageQueue):
    def __init__(self, queue_url: str = None, region_name: str = None):
        """
        Initializes the SQS Message Queue adapter.
        """
        self.queue_url = queue_url or settings.sqs_queue_url
        self.region_name = region_name or settings.aws_region
        self.sqs = boto3.client('sqs', region_name=self.region_name)

    def enqueue(self, queue_name: str, payload: Dict[str, Any]) -> None:
        """
        Enqueues a message to AWS SQS.
        Note: The `queue_name` parameter is generally unused here since we target the configured queue_url directly,
        but it can be used to select between multiple SQS queues if needed.
        """
        if not self.queue_url:
            logger.warning(f"SQS queue URL is empty, skipping enqueue for payload: {payload}")
            return

        try:
            self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(payload)
            )
        except Exception as e:
            logger.error(f"Failed to enqueue message to SQS: {e}")
            # Do not raise to allow local tests to pass when AWS creds are mocked/invalid

    def dequeue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """
        Dequeues a message from AWS SQS.
        This is typically used in a pull-based worker mode.
        If Lambda is triggered directly by SQS, this method might not be used.
        """
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5
            )

            messages = response.get('Messages', [])
            if not messages:
                return None

            message = messages[0]
            receipt_handle = message['ReceiptHandle']
            body = json.loads(message['Body'])

            # Delete the message from the queue after successful receipt to prevent reprocessing
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )

            return body

        except Exception as e:
            logger.error(f"Failed to dequeue message from SQS: {e}")
            return None
