def update_context_prompt():
    content = """TASK: Extract specific data from the resume for a target field.

FIELD NAME:
{{ field_name }}

FIELD MEANING:
{{ field_meaning }}

SOURCE HINTS:
{{ source_hints }}

TARGET SCHEMA FORMAT:
{{ target_schema }}

TARGET TEMPLATE CONTEXT (Where the data will go):
{{ template_text_excerpt }}

REFINED EXTRACTION CONTEXT (From parsing tools):
{{ structured_context }}

RAW RESUME TEXT:
{{ extracted_text }}

SPECIFIC FORMATTING GUIDANCE:
{{ formatting_guidance }}

CRITICAL RULES:
1. Extract data specifically for the requested FIELD NAME, using the FIELD MEANING and SOURCE HINTS as guidance.
2. Ensure the output strictly conforms to the TARGET SCHEMA FORMAT (a JSON object with the field name as the key).
3. Fill the TARGET SCHEMA using only facts from the document.
4. Prioritize accuracy for names, dates, and companies.
5. Maintain original technical terminology.
6. Output ONLY valid JSON.
"""
    with open('backend/app/agent/prompts/context_aware_extraction.jinja2', 'w') as f:
        f.write(content)
    print("Updated context_aware_extraction.jinja2")

update_context_prompt()
