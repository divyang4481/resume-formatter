from typing import Any, Dict, Optional
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.domain.interfaces import MessageQueue
from app.db.models import LocalQueueMessage

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
        # In a real system, you would lock the row to prevent concurrent processing.
        # This is a lightweight local emulator.
        message = self.db.query(LocalQueueMessage).filter(
            LocalQueueMessage.queue_name == queue_name,
            LocalQueueMessage.status == "pending"
        ).order_by(LocalQueueMessage.created_at.asc()).first()

        if message:
            message.status = "processing"
            message.processed_at = datetime.utcnow()
            self.db.commit()
            return json.loads(message.payload_json)

        return None
