from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.models import TemplateTestRun as TemplateTestRunModel
from app.schemas.template import TemplateTestRun # assuming we add a schema for this
from datetime import datetime

class SqlAlchemyTemplateGovernanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_audit_record(self, id: str) -> Optional[TemplateTestRunModel]:
        return self.db.query(TemplateTestRunModel).filter(TemplateTestRunModel.id == id).first()

    def get_audits_for_template(self, template_id: str) -> List[TemplateTestRunModel]:
        return self.db.query(TemplateTestRunModel).filter(TemplateTestRunModel.template_id == template_id).all()

    def save_audit_record(self, audit_record: TemplateTestRunModel) -> str:
        # Check if already exists
        existing = self.db.query(TemplateTestRunModel).filter(TemplateTestRunModel.id == audit_record.id).first()
        if not existing:
            self.db.add(audit_record)
        else:
            # Transfer updates from the detached record
            existing.generated_summary = audit_record.generated_summary
            existing.validation_result_json = audit_record.validation_result_json
            existing.output_doc_path = audit_record.output_doc_path
            existing.decision = audit_record.decision
            existing.reviewed_at = audit_record.reviewed_at
            existing.review_notes = audit_record.review_notes
        
        self.db.commit()
        return audit_record.id

