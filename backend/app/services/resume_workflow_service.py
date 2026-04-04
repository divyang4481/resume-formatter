from typing import Any, Dict, Optional
from app.domain.interfaces import LlmRuntimeAdapter
from app.domain.interfaces import DocumentExtractionService, StorageProvider
from app.adapters.repositories.job_repository import JobRepository
from app.adapters.repositories.template_repository import TemplateRepository
from app.schemas.enums import JobStatus
from app.agent.graph import build_workflow_graph, AgentState
from app.agent.state import AgentState as TypedAgentState
from app.dependencies import get_storage_provider

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
        self.graph = build_workflow_graph(
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
        
        template = None
        # Reconstruct context from job metadata
        ext_meta = getattr(job, 'extension_metadata', {})
        if not isinstance(ext_meta, dict):
            ext_meta = {}

        intent = ext_meta.get("intent", "candidate_runtime")
        actor_role = ext_meta.get("actor_role", "system")
        filename = ext_meta.get("filename", "document.pdf")
        content_type = ext_meta.get("content_type", "application/pdf")
        selected_template_id = getattr(job, 'selected_template_id', None)

        # Fetch template-specific AI steering guidance
        summary_guidance = ""
        formatting_guidance = ""
        validation_guidance = ""
        pii_guidance = ""
        industry = ext_meta.get("industry_id", "General")
        language = "en"

        if selected_template_id and self.template_repo:
            try:
                template = self.template_repo.get_template(selected_template_id)
                if template:
                    summary_guidance = template.summary_guidance or ""
                    formatting_guidance = template.formatting_guidance or ""
                    validation_guidance = template.validation_guidance or ""
                    pii_guidance = template.pii_guidance or ""
                    industry = template.industry or industry
                    language = template.language or "en"
            except Exception as te:
                print(f"Warning: Failed to fetch template guidance for {selected_template_id}: {te}")

        # Initial state for the LangGraph execution
        initial_state: TypedAgentState = {
            "session_id": job_id,
            "file_path": getattr(job, 'original_file_ref', f"jobs/{job_id}/input/{filename}"),
            "file_type": "auto",
            "extracted_text": None,
            "extraction_confidence": None,
            "canonical_model": None,
            "privacy_transformed_model": None,
            "selected_template_id": selected_template_id,
            "template_storage_uri": None,
            "formatting_guidance": formatting_guidance,
            "summary_guidance": summary_guidance,
            "validation_guidance": validation_guidance,
            "pii_guidance": pii_guidance,
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
            "runtime_metadata": ext_meta,
            "expected_sections": getattr(template, 'expected_sections', "") if template else "",
            "expected_fields": getattr(template, 'expected_fields', "") if template else "",
            "field_extraction_manifest": getattr(template, 'field_extraction_manifest', []) if template else []
        }

        try:
            # Execute the workflow
            final_state = await self.graph.ainvoke(initial_state)

            final_status = final_state.get("status")

            if final_status == "WAITING_FOR_CONFIRMATION":
                job.status = JobStatus.WAITING_FOR_CONFIRMATION
            elif final_status == "REJECTED_INVALID_DOCUMENT":
                job.status = JobStatus.FAILED
                job.error_message = final_state.get("document_reason") or "Invalid document"
            else:
                job.status = JobStatus.COMPLETED

            # Persist triage outcomes to job extension metadata
            ext_meta["document_kind"] = final_state.get("document_kind")
            ext_meta["document_confidence"] = final_state.get("document_confidence")
            ext_meta["document_reason"] = final_state.get("document_reason")
            ext_meta["suggested_template_ids"] = final_state.get("suggested_template_ids")
            ext_meta["suggested_template_scores"] = final_state.get("suggested_template_scores")
            job.extension_metadata = ext_meta

            if final_state.get("selected_template_id"):
                job.selected_template_id = final_state["selected_template_id"]

            if final_state.get("summary_uri"):
                job.summary_uri = final_state["summary_uri"]
            if final_state.get("summary_text"):
                job.generated_summary = final_state["summary_text"]
            if final_state.get("render_docx_uri"):
                job.render_docx_uri = final_state["render_docx_uri"]

            # If it's a governance audit run, update the audit record
            test_run_id = ext_meta.get("test_run_id")
            if test_run_id:
                from app.db.session import SessionLocal
                from app.adapters.repositories.template_governance_repository import SqlAlchemyTemplateGovernanceRepository
                import json
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
