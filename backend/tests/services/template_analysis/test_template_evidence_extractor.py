import pytest
import io
import zipfile
from app.services.template_analysis.template_evidence_extractor import TemplateEvidenceExtractor

def create_mock_docx(xml_content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("word/document.xml", xml_content)
    return buffer.getvalue()

@pytest.mark.asyncio
async def test_extract_evidence_sequences_and_bullet_sections():
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p>
                <w:pStyle w:val="Heading1"/>
                <w:r><w:t>WORK EXPERIENCE</w:t></w:r>
            </w:p>
            <w:p><w:r><w:t>"[Job description, Date]"</w:t></w:r></w:p>
            <w:p><w:r><w:t>[Organisation]</w:t></w:r></w:p>
            <w:p><w:r><w:t>"[Bullet point responsibilities]"</w:t></w:r></w:p>

            <w:p><w:r><w:t>"[Job description, Date]"</w:t></w:r></w:p>
            <w:p><w:r><w:t>[Organisation]</w:t></w:r></w:p>
            <w:p><w:r><w:t>"[Bullet point responsibilities]"</w:t></w:r></w:p>

            <w:p>
                <w:pStyle w:val="Heading1"/>
                <w:r><w:t>Key skills</w:t></w:r>
            </w:p>
            <w:p><w:numPr><w:ilvl w:val="0"/></w:numPr><w:r><w:t>·</w:t></w:r></w:p>
            <w:p><w:numPr><w:ilvl w:val="0"/></w:numPr><w:r><w:t>·</w:t></w:r></w:p>

            <w:p>
                <w:pStyle w:val="Heading1"/>
                <w:r><w:t>CANDIDATE’S OWN CV</w:t></w:r>
            </w:p>
            <w:p>
                <w:r>
                    <w:rPr><w:color w:val="FF0000"/></w:rPr>
                    <w:t>Paste the candidate’s own CV in this space...</w:t>
                </w:r>
            </w:p>
        </w:body>
    </w:document>
    """

    content = create_mock_docx(xml)
    extractor = TemplateEvidenceExtractor()
    evidence = await extractor.extract(content, "test.docx", {})

    # Assert repeated block detection
    sequences = evidence["placeholder_view"]["repeated_placeholder_sequences"]
    assert len(sequences) == 1
    assert sequences[0]["heading"] == "WORK EXPERIENCE"
    assert '"[Job description, Date]"' in sequences[0]["ordered_placeholders"]

    # Assert paste zone
    paste_zones = evidence["docx_structure_view"]["paste_zones"]
    assert "CANDIDATE’S OWN CV" in paste_zones

    # Assert instruction block
    instructions = evidence["docx_structure_view"]["instruction_blocks"]
    assert "Paste the candidate’s own CV in this space..." in instructions

    # Assert bullet sections
    bullets = evidence["docx_structure_view"]["bullet_sections"]
    assert len(bullets) == 1
    assert bullets[0]["heading"] == "Key skills"
    assert bullets[0]["sample_bullet_count"] == 2
