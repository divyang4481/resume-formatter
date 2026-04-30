from typing import Any, Dict, Optional
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.domain.interfaces import MessageQueue
from app.db.models import LocalQueueMessage
from app.config import settings


logger = logging.getLogger(__name__)

class SqlAlchemyMessageQueue(MessageQueue):
    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, queue_name: str, payload: Dict[str, Any]) -> None:
        message = LocalQueueMessage(
            queue_name=queue_name,
            payload_json=json.dumps(payload),
            status="pending"
        )
        self.db.add(message)
        self.db.commit()

    def dequeue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        # Reclaim stuck processing messages after visibility timeout.
        reclaim_before = datetime.now() - timedelta(seconds=settings.message_queue_visibility_timeout_seconds)

        # Safety gate: allow up to max_parallel_jobs non-expired in-flight messages at a time.
        # This prevents the queue from being overwhelmed while still allowing parallelism.
        active_processing_count = self.db.query(LocalQueueMessage).filter(
            LocalQueueMessage.queue_name == queue_name,
            LocalQueueMessage.status == "processing",
            LocalQueueMessage.processed_at >= reclaim_before,
        ).count()
        
        if active_processing_count >= settings.max_parallel_jobs:
            return None

        message = self.db.query(LocalQueueMessage).filter(
            LocalQueueMessage.queue_name == queue_name,
            or_(
                LocalQueueMessage.status == "pending",
                (LocalQueueMessage.status == "processing") & (LocalQueueMessage.processed_at < reclaim_before)
            )
        ).order_by(LocalQueueMessage.created_at.asc()).first()

        if message:
            message.status = "processing"
            message.processed_at = datetime.now()
            self.db.commit()
            logger.info("DB queue claimed message_id=%s queue=%s", message.id, queue_name)
            payload = json.loads(message.payload_json)
            payload["_queue_message_id"] = message.id
            return payload

        return None

    def mark_completed(self, queue_name: str, message: Dict[str, Any]) -> None:
        message_id = message.get("_queue_message_id")
        if message_id is None:
            return
        row = self.db.query(LocalQueueMessage).filter(
            LocalQueueMessage.id == message_id,
            LocalQueueMessage.queue_name == queue_name
        ).first()
        if row:
            row.status = "completed"
            row.processed_at = datetime.now()
            self.db.commit()

    def mark_failed(self, queue_name: str, message: Dict[str, Any], error: Optional[str] = None) -> None:
        message_id = message.get("_queue_message_id")
        if message_id is None:
            return
        row = self.db.query(LocalQueueMessage).filter(
            LocalQueueMessage.id == message_id,
            LocalQueueMessage.queue_name == queue_name
        ).first()
        if row:
            # Return to pending for retry on transient failures.
            row.status = "pending"
            row.processed_at = datetime.now()
            self.db.commit()
