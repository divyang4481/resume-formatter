import json
import logging
from typing import Dict, Any, Iterable, Optional
from app.domain.interfaces.queue import JobQueue
from app.config import settings
from app.adapters.aws_client import aws_service_client

logger = logging.getLogger(__name__)

class SqsJobQueueAdapter(JobQueue):
    def __init__(self, queue_url: str = None):
        self.queue_url = queue_url or settings.sqs_processing_queue_url
        self.sqs = aws_service_client('sqs', region_name=settings.aws_region)

    def publish(self, message: Dict[str, Any]) -> str:
        try:
            response = self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message)
            )
            msg_id = response.get('MessageId')
            logger.info(f"Successfully published message to SQS: {msg_id} (Queue: {self.queue_url})")
            return msg_id
        except Exception as e:
            logger.error(f"Failed to publish message to SQS: {e}")
            raise

    def consume(self) -> Iterable[Dict[str, Any]]:
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10
            )
            for msg in response.get('Messages', []):
                try:
                    body = json.loads(msg['Body'])
                    yield {
                        "receipt_handle": msg['ReceiptHandle'],
                        "body": body,
                        "message_id": msg['MessageId']
                    }
                except json.JSONDecodeError:
                    logger.warning(f"Skipping non-JSON message {msg['MessageId']}: {msg['Body']}")
                    # Optionally ack it so it doesn't stay in the queue
                    self.ack({"receipt_handle": msg['ReceiptHandle']})
        except Exception as e:
            logger.error(f"Failed to consume message from SQS: {e}")

    def ack(self, message: Any) -> None:
        try:
            receipt_handle = message.get("receipt_handle")
            if receipt_handle:
                self.sqs.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle
                )
        except Exception as e:
            logger.error(f"Failed to ack message to SQS: {e}")

    def nack(self, message: Any, reason: str) -> None:
        try:
            receipt_handle = message.get("receipt_handle")
            if receipt_handle:
                self.sqs.change_message_visibility(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=0
                )
        except Exception as e:
            logger.error(f"Failed to nack message to SQS: {e}")

class LocalJobQueueAdapter(JobQueue):
    _shared_queue = []
    def __init__(self):
        self.queue = self._shared_queue

    def publish(self, message: Dict[str, Any]) -> str:
        msg_id = f"local-{len(self.queue)}"
        self.queue.append({
            "message_id": msg_id,
            "body": message
        })
        return msg_id

    def consume(self) -> Iterable[Dict[str, Any]]:
        if self.queue:
            msg = self.queue.pop(0)
            yield msg

    def ack(self, message: Any) -> None:
        pass # Not needed for simple local mock

    def nack(self, message: Any, reason: str) -> None:
        self.queue.append(message)
