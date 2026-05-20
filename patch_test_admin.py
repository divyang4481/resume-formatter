def update_test():
    with open('backend/tests/unit/test_admin_api.py', 'r') as f:
        content = f.read()

    # In test_upload_asset_success, we have mock extraction logic failing because we updated template analysis.
    # We should mock it to return what's expected now.

    old_test = """            return {"purpose": "Test", "expected_sections": "Summary"}"""
    new_test = """            return {"purpose": "Test", "expected_sections": "Summary", "expected_fields": "foo", "field_extraction_manifest": []}"""

    if old_test in content:
        content = content.replace(old_test, new_test)
        with open('backend/tests/unit/test_admin_api.py', 'w') as f:
            f.write(content)
        print("Updated test_admin_api.py mock return")
    else:
        print("Could not find block in test_admin_api.py")

update_test()
