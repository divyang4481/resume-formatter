from typing import Dict, Any
from app.agent.state import AgentState
from app.domain.interfaces.agent import ResumeFormattingAgent
from app.dependencies import get_agent_provider
import logging

logger = logging.getLogger(__name__)

def create_template_contract_generation_node():
    """
    Node that uses Agentic Core to generate a template contract.
    """
    async def template_contract_generation_node(state: AgentState) -> dict:
        logger.info("Executing Template Contract Generation Node...")
        extracted_text = state.get("extracted_text", "")
        template_metadata = state.get("runtime_metadata", {})

        agent: ResumeFormattingAgent = get_agent_provider()

        try:
            contract = agent.generate_template_contract(
                template_text=extracted_text,
                template_metadata=template_metadata
            )
            return {"canonical_model": contract, "status": "contract_generated"}
        except Exception as e:
            logger.error(f"Template contract generation failed: {e}")
            return {"status": "contract_generation_failed", "validation_errors": [str(e)]}

    return template_contract_generation_node

def create_kb_retrieval_node():
    """
    Node that retrieves KB rules for formatting based on intent or metadata.
    """
    async def kb_retrieval_node(state: AgentState) -> dict:
        logger.info("Executing KB Retrieval Node...")

        # In a real scenario, this would query Bedrock KB or a vector DB.
        # For now, we mock the retrieval step to satisfy the bounded workflow.
        from app.dependencies import get_knowledge_index
        index = get_knowledge_index()

        template_id = state.get("selected_template_id", "default")

        try:
            results = index.retrieve(query=f"formatting rules for template {template_id}", filters={}, top_k=3)
            # Flatten text
            retrieved_guidance = "\n".join([r.get("payload", {}).get("text", "") for r in results])

            return {
                "formatting_guidance": retrieved_guidance or "Default professional formatting",
                "status": "kb_retrieved"
            }
        except Exception as e:
            logger.error(f"KB retrieval failed: {e}")
            return {"formatting_guidance": "", "status": "kb_retrieval_failed"}

    return kb_retrieval_node

def create_output_quality_reasoning_node():
    """
    Node that uses Agentic Core to evaluate output quality.
    """
    async def output_quality_reasoning_node(state: AgentState) -> dict:
        logger.info("Executing Output Quality Reasoning Node...")
        mapped_data = state.get("transformed_document_json") or {}
        # Ensure it is a dict
        if isinstance(mapped_data, str):
            import json
            try:
                mapped_data = json.loads(mapped_data)
            except:
                mapped_data = {}

        template_contract = state.get("canonical_model")
        if not template_contract:
            template_contract = state.get("field_extraction_manifest")
        
        if not template_contract and state.get("expected_fields"):
            # Fallback to simple list of fields if no rich manifest
            fields = [f.strip() for f in state.get("expected_fields").split(",") if f.strip()]
            template_contract = [{"fieldname": f, "meaning": f} for f in fields]

        if not template_contract and state.get("selected_template"):
            template_obj = state.get("selected_template")
            if isinstance(template_obj, dict):
                template_contract = template_obj.get("field_extraction_manifest", {})
        
        template_contract = template_contract or {}
        job_id = state.get("session_id", "default")

        agent: ResumeFormattingAgent = get_agent_provider()

        try:
            evaluation = agent.evaluate_output_quality(
                mapped_data=mapped_data,
                template_contract=template_contract,
                job_context={"job_id": job_id}
            )

            # --- HIGH VISIBILITY QUALITY LOGGING ---
            needs_review = evaluation.get("needs_review", False)
            if needs_review:
                logger.warning("\n" + "!"*60 + "\n!!! AI QUALITY GATE ALERT (LOG ONLY) !!!\n" + "!"*60)
                logger.warning(f"REASON: {evaluation.get('reason')}")
                logger.warning(f"SUGGESTED ACTION: {evaluation.get('suggested_admin_action')}")
                logger.warning("!"*60 + "\n")
            else:
                logger.info("\n" + "="*60 + "\n=== AI QUALITY GATE: PASSED ===\n" + "="*60 + "\n")

            # Merge missing fields from evaluation with existing ones in state
            existing_missing = state.get("missing_fields") or []
            new_missing = evaluation.get("missing_fields", [])
            merged_missing = list(set(existing_missing + new_missing))

            # We log the warning but do NOT block the flow for review
            return {
                "requires_human_review": False, 
                "validation_passed": True,
                "validation_warnings": [evaluation.get("reason")] if needs_review else [],
                "missing_fields": merged_missing,
                "status": "quality_evaluated"
            }
        except Exception as e:
            logger.error(f"Output quality evaluation failed: {e}")
            return {"status": "quality_evaluation_failed", "validation_passed": False}

    return output_quality_reasoning_node

def create_summary_generation_node(ai_service, storage):
    """
    Node dedicated to generating a professional CV summary using LLM.
    """
    async def summary_generation_node(state: AgentState) -> dict:
        logger.info("Executing Summary Generation Node...")
        session_id = state.get("session_id", "unknown-session")
        extracted_text = state.get("extracted_text", "")
        
        if not extracted_text:
            return {"status": "summary_failed", "summary_text": "No extracted text available for summary."}

        summary_guidance = state.get("summary_guidance") or ""
        industry = state.get("industry")
        language = state.get("language", "en")

        try:
            summary_text = await ai_service.generate_summary(
                extracted_text=extracted_text,
                guidance=summary_guidance,
                industry=industry,
                language=language,
            )
            
            # Persist summary to storage as an artifact
            from app.agent.utils.llm_sanitizer import LlmSanitizer
            clean_summary = LlmSanitizer.strip_cvml(summary_text)
            
            summary_key = f"jobs/{session_id}/output/summary.md"
            final_summary_md = f"### CV Summary\n\n{clean_summary}"
            summary_uri = storage.put_bytes(
                final_summary_md.encode("utf-8"), summary_key
            )
            
            return {
                "summary_text": clean_summary,
                "summary_uri": summary_uri,
                "status": "summary_generated"
            }
        except Exception as e:
            logger.error(f"Summary generation node failed: {e}")
            return {"status": "summary_failed"}

    return summary_generation_node

def create_missing_fields_identification_node():
    """
    Node that explicitly identifies missing fields by comparing 
    harmonized data against the template manifest.
    """
    async def missing_fields_identification_node(state: AgentState) -> dict:
        logger.info("Executing Missing Fields Identification Node...")
        
        # 1. Get harmonized data
        transformed_data = state.get("transformed_document_json")
        if isinstance(transformed_data, str):
            import json
            try:
                transformed_data = json.loads(transformed_data)
            except:
                transformed_data = {}
        
        precomputed_missing = []
        mapping_results = {}
        if isinstance(transformed_data, dict):
            precomputed_missing = transformed_data.get("missing_fields_requiring_recruiter_or_ats_input") or []
            mapping_results = transformed_data.get("template_fill_result", {}) or {}
        
        # 2. Get manifest
        manifest = state.get("field_extraction_manifest") or []
        if isinstance(manifest, str):
            import json
            try:
                manifest = json.loads(manifest)
            except:
                manifest = []
        
        # 3. Compare
        missing_fields = list(precomputed_missing) if isinstance(precomputed_missing, list) and precomputed_missing else []
        for field in manifest:
            fname = field.get("fieldname")
            if not fname or field.get("field_type") == "instruction_block":
                continue
            entry = mapping_results.get(fname)
            if isinstance(entry, dict):
                status = entry.get("status") or (entry.get("field_extraction_manifest") or {}).get("status")
                value = entry.get("value")
                if value is None:
                    value = (entry.get("field_extraction_manifest") or {}).get("value")
                is_missing = status in ("not_found", "needs_user_input") or value in (None, "", [], {})
            else:
                is_missing = entry in (None, "", [], {})
            if is_missing and fname not in missing_fields:
                missing_fields.append(fname)
        
        logger.info(f"Identified {len(missing_fields)} missing fields.")
        
        return {
            "missing_fields": missing_fields,
            "status": "missing_fields_identified"
        }
    return missing_fields_identification_node
