def update_template_resolution():
    with open('backend/app/agent/nodes/template_resolution_node.py', 'r') as f:
        content = f.read()

    old_fetch = """            if template_meta:
                storage_uri = template_meta.original_file_ref
                summary_guidance = template_meta.summary_guidance
                formatting_guidance = template_meta.formatting_guidance
                validation_guidance = template_meta.validation_guidance
                pii_guidance = template_meta.pii_guidance
                expected_sections = template_meta.expected_sections
                expected_fields = template_meta.expected_fields
                print(f"Found template storage URI: {storage_uri}")"""

    new_fetch = """            if template_meta:
                import json
                storage_uri = template_meta.original_file_ref
                summary_guidance = template_meta.summary_guidance
                formatting_guidance = template_meta.formatting_guidance
                validation_guidance = template_meta.validation_guidance
                pii_guidance = template_meta.pii_guidance
                expected_sections = template_meta.expected_sections
                expected_fields = template_meta.expected_fields

                field_extraction_manifest = []
                if hasattr(template_meta, 'field_extraction_manifest') and template_meta.field_extraction_manifest:
                    try:
                        if isinstance(template_meta.field_extraction_manifest, str):
                            field_extraction_manifest = json.loads(template_meta.field_extraction_manifest)
                        else:
                            field_extraction_manifest = template_meta.field_extraction_manifest
                    except Exception as e:
                        print(f"Warning: Could not parse field_extraction_manifest: {e}")

                print(f"Found template storage URI: {storage_uri}")"""

    if old_fetch in content:
        content = content.replace(old_fetch, new_fetch)
        print("Updated fetch block in template_resolution_node.py")
    else:
        print("Could not find fetch block")

    old_else = """            else:
                print(f"Warning: Template ID {chosen_template_id} not found in database.")
                expected_sections = None
                expected_fields = None"""

    new_else = """            else:
                print(f"Warning: Template ID {chosen_template_id} not found in database.")
                expected_sections = None
                expected_fields = None
                field_extraction_manifest = []"""

    if old_else in content:
        content = content.replace(old_else, new_else)
        print("Updated else block in template_resolution_node.py")

    old_return = """                "expected_sections": expected_sections,
                "expected_fields": expected_fields,
                "status": "template_resolved"
            }"""

    new_return = """                "expected_sections": expected_sections,
                "expected_fields": expected_fields,
                "field_extraction_manifest": field_extraction_manifest,
                "status": "template_resolved"
            }"""

    if old_return in content:
        content = content.replace(old_return, new_return)
        print("Updated return block in template_resolution_node.py")

    with open('backend/app/agent/nodes/template_resolution_node.py', 'w') as f:
        f.write(content)

update_template_resolution()
