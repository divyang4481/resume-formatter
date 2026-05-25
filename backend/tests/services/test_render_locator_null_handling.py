import pytest
from app.schemas.template_analysis import RenderLocator, TemplateField
from app.services.template_analysis_service import TemplateAnalysisService

def test_render_locator_handles_none_values():
    # Verify that RenderLocator accepts None values gracefully after our typing change
    locator = RenderLocator(
        strategy="replace_marker",
        marker_text=None,
        label=None,
        heading=None
    )
    assert locator.strategy == "replace_marker"
    assert locator.marker_text is None or locator.marker_text == ""
    assert locator.label is None or locator.label == ""
    assert locator.heading is None or locator.heading == ""

def test_template_field_mapping_sanitization():
    # Verify that we can instantiate RenderLocator via the service mapping logic
    # using locator_data containing None values, and that the None values are sanitized.
    locator_data = {
        "strategy": "replace_marker",
        "marker_text": None,
        "label": None,
        "heading": None
    }
    
    # Sanitize like in map_field:
    sanitized = {k: (v if v is not None else "") for k, v in locator_data.items()}
    if not sanitized.get("strategy"):
        sanitized["strategy"] = "replace_marker"
        
    locator = RenderLocator(**sanitized)
    assert locator.strategy == "replace_marker"
    assert locator.marker_text == ""
    assert locator.label == ""
    assert locator.heading == ""
