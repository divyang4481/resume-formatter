import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from app.agent.state import AgentState
from app.agent.nodes.template_resolution_node import create_template_resolve_node

@pytest.mark.asyncio
async def test_template_resolution_node_uses_cache_and_bypasses_docling():
    # 1. Setup mocks
    llm_runtime = MagicMock()
    storage_provider = MagicMock()
    doc_parser = MagicMock()
    doc_parser.extract = AsyncMock() # This should NOT be called

    # Mock template database record
    mock_template = MagicMock()
    mock_template.id = "test-template-id"
    mock_template.storage_uri = "local://templates/test.docx"
    mock_template.summary_guidance = "Summary guide"
    mock_template.formatting_guidance = "Formatting guide"
    mock_template.validation_guidance = "Validation guide"
    mock_template.pii_guidance = "PII guide"
    mock_template.expected_sections = "Section1,Section2"
    mock_template.expected_fields = "Field1,Field2"
    mock_template.field_extraction_manifest = json.dumps([{"fieldname": "Field1", "marker_text": "M1"}])
    
    # Store docling_markdown in analysis_json cache
    analysis_data = {
        "template_id": "test-template-id",
        "docling_markdown": "# Mock Template Markdown Content\nWith placeholders «Field1»"
    }
    mock_template.analysis_json = json.dumps(analysis_data)

    # 2. Patch DB session and repository
    mock_session = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_template.return_value = mock_template
    
    # Patch SessionLocal to return mock_session and SqlAlchemyTemplateRepository to return mock_repo
    with patch("app.agent.nodes.template_resolution_node.SessionLocal", return_value=mock_session), \
         patch("app.agent.nodes.template_resolution_node.SqlAlchemyTemplateRepository", return_value=mock_repo):
         
        # Create the node
        node = create_template_resolve_node(llm_runtime, storage_provider, doc_parser)
        
        # Define agent state
        state: AgentState = {
            "session_id": "test-session-id",
            "extracted_text": "Resume text",
            "template_asset_id": "test-template-id"
        }
        
        # Run the node
        result = await node(state)
        
        # 3. Assertions
        # Verify doc_parser.extract was NOT called because of the bypass!
        doc_parser.extract.assert_not_called()
        
        # Verify storage_provider was NOT called to fetch bytes either!
        storage_provider.get_bytes.assert_not_called()
        
        # Verify the returned template text is the cached markdown
        assert result["template_text"] == "# Mock Template Markdown Content\nWith placeholders «Field1»"
        assert result["template_asset_id"] == "test-template-id"
        assert result["status"] == "template_resolved"
