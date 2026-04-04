import json
import logging
from datetime import datetime
from typing import Any, Dict

from app.config import settings
from app.db.session import SessionLocal
from app.db.models import AuditEvent
import uuid

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log_event(job_id: str, event_type: str, payload: Dict[str, Any], actor: str = "system", entity_type: str = "ProcessingJob"):
        """
        Logs an event to the AuditEvent table if ENABLE_AUDIT_LOGGING is true.
        The entity_id will be the job_id, entity_type will be 'ProcessingJob' or provided type.
        The action will be the event_type.
        """
        if not settings.enable_audit_logging:
            return

        # Typically we would pass in a db session but because these logs are deeply
        # embedded in graph nodes that don't easily have session references passed in,
        # we will use a distinct session. Since this was raised in code review, we
        # have optimized it where possible but given the current constraints, we leave it.
        # However, to be more robust, we ensure db closing.
        db = SessionLocal()
        try:
            # Fallback for job_id if None to avoid DB IntegrityError
            safe_job_id = job_id if job_id else "unknown-session"
            payload_json = json.dumps(payload, default=str)

            audit_event = AuditEvent(
                id=str(uuid.uuid4()),
                entity_type=entity_type,
                entity_id=safe_job_id,
                action=event_type,
                actor=actor,
                payload_json=payload_json,
                created_at=datetime.utcnow()
            )

            db.add(audit_event)
            db.commit()
            logger.info(f"Audit log captured in DB for job_id={safe_job_id}, event_type={event_type}")
        except Exception as e:
            logger.error(f"Failed to capture audit log for job_id={job_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()
