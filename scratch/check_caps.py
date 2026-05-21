import sys
import os
sys.path.append(os.path.abspath('backend'))
from docx import Document
doc = Document(r'SampleData\templates\UK Worldwide London.docx')
for i, p in enumerate(doc.paragraphs):
    if "WORK" in p.text.upper():
        print(f"Para {i}: text='{p.text}'")
        for run in p.runs:
            print(f"  Run: '{run.text}', bold={run.bold}, all_caps={run.font.all_caps}")
