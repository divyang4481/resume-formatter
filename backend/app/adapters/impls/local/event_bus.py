import logging
from typing import Any, Dict
from app.domain.interfaces import EventBus

logger = logging.getLogger(__name__)

class LocalEventBus(EventBus):
    """
    A simple local implementation of an event bus and audit logger.
    Useful for local dev, testing, or before a full message queue is wired up.
    """
    def publish(self, topic: str, event: Any) -> None:
        logger.info(f"EVENT PUBLISHED: topic='{topic}', event={event}")

    def audit(self, action: str, details: Dict[str, Any]) -> None:
        logger.info(f"AUDIT ENTRY: action='{action}', details={details}")
