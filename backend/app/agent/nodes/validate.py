from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
import json

def create_validate_node(ai_service: ResumeAiService):
    """
    Creates the LangGraph node for validating the transformed document against
    template-specific rules and guidelines using the centralized AI service.
    """
    async def validate_node(state: AgentState) -> dict:
        print("Executing Validation Node...")

        transformed_json_str = state.get("transformed_document_json", "")
        validation_guidance = state.get("validation_guidance") or "Check structural integrity and placeholder leaks."
        
        if not transformed_json_str:
            return {"status": "validation_skipped", "validation_passed": False}

        try:
            # Parse the current transformed JSON
            transformed_data = json.loads(transformed_json_str)
            
            # Delegate semantic validation to the specialized AI service
            validation_result = await ai_service.validate_output(
                transformed_data=transformed_data,
                guidance=validation_guidance
            )
            
            passed = validation_result.get("status") == "PASS"
            errors = validation_result.get("errors", [])
            
            # If the transformation node already flagged placeholders, we should carry those over
            if not state.get("validation_passed", True):
                prev_errors = state.get("validation_errors") or []
                errors.extend(prev_errors)
                passed = False

            return {
                "validation_passed": passed,
                "validation_errors": errors,
                "status": "validated" if passed else "validation_failed"
            }
        except Exception as e:
            print(f"Error during AI semantic validation: {e}")
            return {
                "validation_passed": False,
                "validation_errors": [f"Semantic validation failure: {str(e)}"],
                "status": "validation_failed"
            }

    return validate_node
