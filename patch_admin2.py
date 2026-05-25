import re

def update_admin2():
    with open('backend/app/api/admin.py', 'r') as f:
        content = f.read()

    # Need to handle JSON serialization for field_extraction_manifest in update_template
    old_update = """        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(template, key, value)"""

    new_update = """        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "field_extraction_manifest" and value is not None:
                setattr(template, key, json.dumps(value))
            else:
                setattr(template, key, value)"""

    if old_update in content:
        content = content.replace(old_update, new_update)
        print("Updated update loop in admin.py")


    old_return = """                "expected_sections": template.expected_sections,
                "expected_fields": template.expected_fields,
                "summary_guidance": template.summary_guidance,"""

    new_return = """                "expected_sections": template.expected_sections,
                "expected_fields": template.expected_fields,
                "field_extraction_manifest": json.loads(template.field_extraction_manifest) if template.field_extraction_manifest else [],
                "summary_guidance": template.summary_guidance,"""

    if old_return in content:
        content = content.replace(old_return, new_return)
        print("Updated get_template_detail return in admin.py")

    with open('backend/app/api/admin.py', 'w') as f:
        f.write(content)

update_admin2()
