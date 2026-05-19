import logging
import json
import uuid
from typing import Any, Dict, Optional
from app.domain.interfaces import LlmRuntimeAdapter
from app.domain.interfaces import DocumentExtractionService, StorageProvider
from app.adapters.repositories.job_repository import JobRepository
from app.adapters.repositories.template_repository import TemplateRepository
from app.schemas.enums import JobStatus
from app.agent.graph import build_resume_processing_graph, AgentState
from app.agent.state import AgentState as TypedAgentState
from app.dependencies import get_storage_provider
from app.services.template_manifest_utils import normalize_template_manifest

logger = logging.getLogger(__name__)

class ResumeWorkflowService:
    def __init__(
        self, 
        llm: LlmRuntimeAdapter, 
        parser_service: DocumentExtractionService, 
        job_repo: JobRepository,
        template_repo: Optional[TemplateRepository] = None,
        storage: Optional[StorageProvider] = None
    ):
        self.llm = llm
        self.parser_service = parser_service
        self.job_repo = job_repo
        self.template_repo = template_repo
        self.storage = storage or get_storage_provider()
        
        # Build the graph once for this service instance
        self.graph = build_resume_processing_graph(
            llm_runtime=self.llm, 
            doc_parser=self.parser_service, 
            storage=self.storage,
            job_repo=self.job_repo
        )

    async def execute_job(self, job_id: str):
        """
        Executes the full agentic workflow for a specific processing job.
        Updates the database status and stage in real-time.
        """
        job = self.job_repo.get_job(job_id)
        if not job:
            print(f"Error: Job {job_id} not found for execution.")
            return

        job.status = JobStatus.PROCESSING
        self.job_repo.save_job(job)

        # Reconstruct context from job metadata
        ext_meta = getattr(job, 'extension_metadata', {})
        if not isinstance(ext_meta, dict):
            ext_meta = {}

        intent = ext_meta.get("intent", "candidate_runtime")
        actor_role = ext_meta.get("actor_role", "system")
        filename = ext_meta.get("filename", "document.pdf")
        content_type = ext_meta.get("content_type", "application/pdf")
        template_asset_id = getattr(job, 'template_asset_id', None)

        # Fetch template-specific AI steering guidance
        summary_guidance = ""
        formatting_guidance = ""
        validation_guidance = ""
        pii_guidance = ""
        analysis_json = ""
        industry = ext_meta.get("industry_id", "General")
        language = "en"

        field_extraction_manifest = None
        expected_fields = ""
        template_storage_uri = None

        if template_asset_id and self.template_repo:
            try:
                template = self.template_repo.get_template(template_asset_id)
                if template:
                    summary_guidance = template.summary_guidance or ""
                    formatting_guidance = template.formatting_guidance or ""
                    validation_guidance = template.validation_guidance or ""
                    pii_guidance = template.pii_guidance or ""
                    analysis_json = template.analysis_json or ""
                    industry = template.industry or industry
                    language = template.language or "en"
                    
                    # --- FIX: Populate extraction contract fields ---
                    manifest_obj = normalize_template_manifest(template.field_extraction_manifest)
                    field_extraction_manifest = manifest_obj
                    expected_fields = template.expected_fields or ",".join(
                        f.get("fieldname", "")
                        for f in manifest_obj.get("fields", [])
                        if isinstance(f, dict) and f.get("fieldname")
                    )
                    template_storage_uri = template.storage_uri
            except Exception as te:
                print(f"Warning: Failed to fetch template guidance for {template_asset_id}: {te}")

        # Initial state for the LangGraph execution
        initial_state: TypedAgentState = {
            "session_id": job_id,
            "file_path": getattr(job, 'original_file_ref', f"jobs/{job_id}/input/{filename}"),
            "file_type": "auto",
            "extracted_text": None,
            "extraction_confidence": None,
            "canonical_model": None,
            "field_extraction_manifest": field_extraction_manifest,
            "expected_fields": expected_fields,
            "privacy_transformed_model": None,
            "template_asset_id": template_asset_id,
            "template_storage_uri": template_storage_uri,
            "formatting_guidance": formatting_guidance,
            "summary_guidance": summary_guidance,
            "validation_guidance": validation_guidance,
            "pii_guidance": pii_guidance,
            "analysis_json": analysis_json,
            "industry": industry,
            "language": language,
            "transformed_document_json": None,
            "validation_passed": True,
            "validation_errors": [],
            "summary_uri": None,
            "render_docx_uri": None,
            "requires_human_review": False,
            "status": "ingested",
            "intent": intent,
            "actor_role": actor_role,
            "filename": filename,
            "content_type": content_type,
            "runtime_metadata": ext_meta
        }

        try:
            # Execute the workflow
            final_state = await self.graph.ainvoke(initial_state)

            # Persist final state back to job
            if final_state.get("template_asset_id"):
                job.template_asset_id = final_state["template_asset_id"]
            
            if final_state.get("summary_uri"):
                job.summary_uri = final_state["summary_uri"]
            if final_state.get("summary_text"):
                job.generated_summary = final_state["summary_text"]
                # Explicitly store summary in CandidateResume if linked
                if job.candidate_resume_id:
                    from app.db.session import SessionLocal
                    from app.db.models import CandidateResume
                    with SessionLocal() as session:
                        candidate = session.query(CandidateResume).filter(CandidateResume.id == job.candidate_resume_id).first()
                        if candidate:
                            candidate.resume_summary = final_state["summary_text"]
                            # Also store the extracted structured data
                            raw_facts = final_state.get("raw_parsed_data")
                            if raw_facts:
                                candidate.candidate_facts_json = json.dumps(raw_facts) if isinstance(raw_facts, dict) else str(raw_facts)

                            extracted_json = final_state.get("transformed_document_json")
                            if extracted_json:
                                if isinstance(extracted_json, dict) and "filled_template_manifest" in extracted_json:
                                    candidate.normalized_resume_json = json.dumps(extracted_json["filled_template_manifest"])
                                else:
                                    candidate.normalized_resume_json = json.dumps(extracted_json) if isinstance(extracted_json, dict) else str(extracted_json)
                            session.commit()
            if final_state.get("render_docx_uri"):
                job.render_docx_uri = final_state["render_docx_uri"]
            
            if final_state.get("summary_uri"):
                job.summary_uri = final_state["summary_uri"]
            
            if final_state.get("summary_text"):
                job.generated_summary = final_state["summary_text"]

            # Persist intermediate JSONs for "Deep Review" UI
            if final_state.get("raw_parsed_data"):
                job.candidate_facts_json = json.dumps(final_state["raw_parsed_data"])
            if final_state.get("transformed_document_json"):
                transformed_data = final_state["transformed_document_json"]
                if isinstance(transformed_data, dict):
                    if "filled_template_manifest" in transformed_data:
                        job.transformed_json = json.dumps(transformed_data["filled_template_manifest"])
                    else:
                        job.transformed_json = json.dumps(transformed_data)
                else:
                    job.transformed_json = str(transformed_data)

            # Determine final status: If it passed quality reasoning node with 'needs_review', use partial success
            if final_state.get("status") == "needs_review" or final_state.get("missing_fields"):
                job.status = JobStatus.PARTIAL_SUCCESS
                logger.info(f"Job {job_id} marked as PARTIAL_SUCCESS due to missing fields or quality reasoning.")
            else:
                job.status = JobStatus.COMPLETED
            missing_fields = final_state.get("missing_fields", [])
            validation_warnings = final_state.get("validation_warnings", [])
            
            if missing_fields or validation_warnings:
                from app.db.session import SessionLocal
                from app.db.models import ValidationResult
                with SessionLocal() as session:
                    # Clean up old results for this job if any
                    session.query(ValidationResult).filter(ValidationResult.job_id == job_id).delete()
                    
                    if missing_fields:
                        session.add(ValidationResult(
                            id=str(uuid.uuid4()),
                            job_id=job_id,
                            validation_type="COMPLETENESS",
                            severity="WARNING",
                            passed=False,
                            message=f"Missing template fields: {', '.join(missing_fields)}",
                            details_json=json.dumps({"missing_fields": missing_fields})
                        ))
                    
                    for warning in validation_warnings:
                        session.add(ValidationResult(
                            id=str(uuid.uuid4()),
                            job_id=job_id,
                            validation_type="QUALITY",
                            severity="INFO",
                            passed=True,
                            message=warning
                        ))
                    session.commit()

            
            # If it's a governance audit run, update the audit record
            test_run_id = ext_meta.get("test_run_id")
            if test_run_id:
                from app.db.session import SessionLocal
                from app.adapters.repositories.template_governance_repository import SqlAlchemyTemplateGovernanceRepository

                db = SessionLocal()
                try:
                    repo = SqlAlchemyTemplateGovernanceRepository(db)
                    audit_record = repo.get_audit_record(test_run_id)
                    
                    if audit_record:
                        # Extract summary text if possible
                        audit_record.generated_summary = final_state.get("summary_text")
                        audit_record.output_doc_path = final_state.get("render_docx_uri")
                        
                        # Set validation results if available
                        if final_state.get("validation_errors") or final_state.get("validation_passed") is not None:
                            val_res = {
                                "passed": final_state.get("validation_passed", False),
                                "errors": final_state.get("validation_errors", []),
                                "warnings": [] # Could be extracted from state if nodes provide them
                            }
                            audit_record.validation_result_json = json.dumps(val_res)
                        
                        repo.save_audit_record(audit_record)
                except Exception as tre:
                    print(f"Warning: Failed to update Governance Audit Record {test_run_id}: {tre}")
                finally:
                    db.close()

            
            self.job_repo.save_job(job)
            return final_state
        except Exception as e:
            print(f"Error executing graph for job {job_id}: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            self.job_repo.save_job(job)
            raise e
