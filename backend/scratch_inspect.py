import os
import zipfile
import lxml.etree as ET
import json
from app.services.template_structure_extractor import TemplateStructureExtractor, _para_text, W_NS, W, NS

def inspect(docx_path):
    print(f"Extracting structure from {docx_path}...")
    with open(docx_path, "rb") as f:
        content = f.read()
    
    extractor = TemplateStructureExtractor()
    struct = extractor.extract(content, os.path.basename(docx_path))
    
    print("\n--- Extracted Structure JSON ---")
    print(json.dumps(struct.to_dict(), indent=2))

if __name__ == "__main__":
    template_path = "../SampleData/templates/UK Worldwide London.docx"
    inspect(template_path)


