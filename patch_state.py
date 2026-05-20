def update_state():
    with open('backend/app/agent/state.py', 'r') as f:
        content = f.read()

    old_fields = """    # Governance Requirements
    expected_sections: Optional[str]
    expected_fields: Optional[str]"""

    new_fields = """    # Governance Requirements
    expected_sections: Optional[str]
    expected_fields: Optional[str]
    field_extraction_manifest: Optional[list]"""

    if old_fields in content:
        content = content.replace(old_fields, new_fields)
        with open('backend/app/agent/state.py', 'w') as f:
            f.write(content)
        print("Updated AgentState in state.py")
    else:
        print("Could not find block in state.py")

update_state()
