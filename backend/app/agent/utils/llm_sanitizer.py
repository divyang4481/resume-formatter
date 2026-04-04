import re
import logging
from typing import Any, List, Optional, Dict

logger = logging.getLogger(__name__)

class LlmSanitizer:
    """
    Utility to clean and sanitize LLM responses across different models (Ollama, GPT, etc.)
    Ensures that conversational noise, markdown blocks, and preambles are removed.
    """

    @staticmethod
    def clean_json(response: str) -> str:
        """
        Robustly extracts the FIRST valid JSON object or list from an LLM response.
        Handles nested brackets and conversational preamble/epilogue correctly.
        """
        if not response:
            return ""
            
        cleaned = response.strip()
        
        # 1. Handle Markdown JSON blocks
        if "```json" in cleaned:
            parts = cleaned.split("```json")
            if len(parts) > 1:
                cleaned = parts[1].split("```")[0].strip()
        elif "```" in cleaned:
            parts = cleaned.split("```")
            if len(parts) > 1:
                cleaned = parts[1].split("```")[0].strip()
        
        # 2. Extract content between first { or [ and its MATCHING closing bracket
        # This prevents "Extra data" errors when the LLM returns multiple blocks
        # or conversational text after the JSON.
        first_open = cleaned.find("{")
        first_list = cleaned.find("[")
        
        # Determine if we have an object or a list first
        start = -1
        open_char, close_char = "", ""
        if first_open != -1 and (first_list == -1 or first_open < first_list):
            start = first_open
            open_char, close_char = "{", "}"
        elif first_list != -1:
            start = first_list
            open_char, close_char = "[", "]"
            
        if start != -1:
            # Find matching closing bracket
            bracket_count = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == open_char:
                    bracket_count += 1
                elif cleaned[i] == close_char:
                    bracket_count -= 1
                    if bracket_count == 0:
                        return cleaned[start : i + 1]
            
            # Fallback if no matching bracket found: return everything from start to last close
            end = cleaned.rfind(close_char)
            if end != -1:
                return cleaned[start : end + 1]
            
        return cleaned

    @staticmethod
    def clean_text(response: str, tag: Optional[str] = None) -> str:
        """
        Cleans free-text responses from LLMs. 
        Optionally extracts content from a specific tag (e.g. <summary>).
        Also filters out common conversational noise like "Here is your output...".
        """
        if not response:
            return ""

        # 1. If a tag is provided, try to extract from it first
        if tag:
            pattern = rf'<{tag}>(.*?)</{tag}>'
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # 2. Fallback: Split into lines and filter conversational headers
        lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
        if not lines:
            return ""

        # Filter common talkative model prefixes (especially Ollama/Llama-based)
        noise_prefixes = ["here is", "here's", "generate", "sure,", "certainly", "ok,", "summary:"]
        
        # Check if the first line looks like a conversational preamble
        first_line_lower = lines[0].lower()
        if any(first_line_lower.startswith(p) for p in noise_prefixes) or (first_line_lower.endswith(":") and len(lines[0]) < 100):
            # If the first line is short and ends with a colon, or starts with noise, skip it
            return "\n".join(lines[1:]).strip()
            
        return response.strip()

    @staticmethod
    def extract_tagged_blocks(text: str) -> Dict[str, str]:
        """
        Hyper-Resilient Harvester: Captures blocks even if the AI adds 
        bolding (**) or forgets closing tags.
        """
        if not text:
            return {}

        raw_results = {}
        # Regex: Matches [MARKER :: Name] possibly wrapped in **
        # Captures until [/MARKER] OR until the next [MARKER :: or end of string
        pattern = r"(?:\*\*)?\[MARKER\s*::\s*(.*?)\](?:\*\*)?(.*?)(?=\[MARKER\s*::|\[/MARKER\]|\Z)"
        
        matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)

        for match in matches:
            name = match.group(1).strip()
            # Clean name from any trailing bolding markers the AI trapped inside
            name = name.replace("**", "").strip()
            
            content = match.group(2).strip()
            # Clean content from trailing [MARKER artifact if regex lookahead was too broad
            content = re.sub(r'\[MARKER\s*::.*', '', content, flags=re.IGNORECASE | re.DOTALL).strip()
            
            if name not in raw_results:
                raw_results[name] = []
            raw_results[name].append(content)

        final_results = {}
        for name, contents in raw_results.items():
            joined_content = "\n\n".join(contents)
            final_results[name] = joined_content
            
            # Alias Support for snake_case placeholders
            snake_name = name.lower().replace(" ", "_")
            if snake_name not in final_results:
                final_results[snake_name] = joined_content

        if not final_results:
            final_results["__raw_content__"] = text

        return final_results

    @staticmethod
    def strip_cvml(text: str) -> str:
        """
        Ruthlessly removes CVML tags and Marker artifacts for human-facing Web UI.
        """
        if not text:
            return ""
            
        # 1. Kill dangling transport markers [MARKER :: Name] [/MARKER]
        clean_text = re.sub(r'\[MARKER\s*::\s*.*?\]', '', text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\[/MARKER\]', '', clean_text, flags=re.IGNORECASE)
        
        # 2. Kill "Summary tags:" and all :CVML: tags
        clean_text = re.sub(r'(?i)summary\s*tags:.*', '', clean_text)
        clean_text = re.sub(r'\[:.*?:\]', '', clean_text)
        
        return clean_text.strip()
