import re

def update_admin():
    with open('backend/app/api/admin.py', 'r') as f:
        content = f.read()

    # Update TemplateUpdateRequest
    old_req = """class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    role_family: Optional[str] = None
    language: Optional[str] = None
    notes: Optional[str] = None
    purpose: Optional[str] = None
    expected_sections: Optional[str] = None
    expected_fields: Optional[str] = None

    summary_guidance: Optional[str] = None
    formatting_guidance: Optional[str] = None
    validation_guidance: Optional[str] = None
    pii_guidance: Optional[str] = None
    selection_weight: Optional[int] = None
    is_default_for_industry: Optional[bool] = None"""

    new_req = """class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    role_family: Optional[str] = None
    language: Optional[str] = None
    notes: Optional[str] = None
    purpose: Optional[str] = None
    expected_sections: Optional[str] = None
    expected_fields: Optional[str] = None
    field_extraction_manifest: Optional[List[Dict[str, Any]]] = None

    summary_guidance: Optional[str] = None
    formatting_guidance: Optional[str] = None
    validation_guidance: Optional[str] = None
    pii_guidance: Optional[str] = None
    selection_weight: Optional[int] = None
    is_default_for_industry: Optional[bool] = None"""

    if old_req in content:
        content = content.replace(old_req, new_req)
        print("Updated TemplateUpdateRequest in admin.py")
    else:
        print("Could not find TemplateUpdateRequest in admin.py")

    # The update endpoint handles the dict update:
    # update_data = payload.model_dump(exclude_unset=True)
    # for key, value in update_data.items():
    #     setattr(template, key, value)

    # Update get_template_detail to return the field_extraction_manifest
    # But wait, looking at `TemplateAsset` model, `field_extraction_manifest` is a Column(Text), so it needs to be JSON dumped. Let's see if we need to json dump it in the patch.
    # Ah, the payload model is List[Dict], so when applying to model, it will try to set list to a string. Let's fix that.

    with open('backend/app/api/admin.py', 'w') as f:
        f.write(content)

update_admin()
