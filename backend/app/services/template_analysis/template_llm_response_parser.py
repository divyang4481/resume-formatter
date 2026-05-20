import json
import logging
from app.agent.utils.llm_sanitizer import LlmSanitizer

logger = logging.getLogger(__name__)

class TemplateLlmResponseParser:
    def parse(self, raw_response: str) -> dict:
        """
        Parses raw LLM response.
        1. Remove markdown/code fences
        2. Extract first valid JSON object
        3. Parse JSON
        4. If parsing fails, return structured error
        """
        result = {
            "parse_status": "failed",
            "data": {},
            "errors": []
        }

        try:
            cleaned_json = LlmSanitizer.clean_json(raw_response)
            if not cleaned_json:
                result["errors"].append("Cleaned JSON is empty.")
                return result

            parsed_data = json.loads(cleaned_json)
            result["parse_status"] = "success"
            result["data"] = parsed_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            result["errors"].append(f"JSONDecodeError: {str(e)}")
            result["errors"].append("Raw response included for debugging.")
            result["raw_response"] = raw_response
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            result["errors"].append(f"Exception: {str(e)}")

        return result
