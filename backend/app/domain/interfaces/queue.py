from abc import ABC, abstractmethod
from typing import Dict, Any, Iterable, Optional

class JobQueue(ABC):
    @abstractmethod
    def publish(self, message: Dict[str, Any]) -> str:
        """Publishes a message to the queue."""
        pass

    @abstractmethod
    def consume(self) -> Iterable[Dict[str, Any]]:
        """Consumes messages from the queue."""
        pass

    @abstractmethod
    def ack(self, message: Any) -> None:
        """Acknowledges a message, removing it from the queue."""
        pass

    @abstractmethod
    def nack(self, message: Any, reason: str) -> None:
        """Negative acknowledgment, returning message to queue or DLQ."""
        pass
