import asyncio
import os
import re
import zipfile
import lxml.etree as ET
import io

def get_docx_placeholders_from_xml(content: bytes) -> list:
    placeholders = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if 'word/document.xml' in z.namelist():
                xml_content = z.read('word/document.xml')
                root = ET.fromstring(xml_content)
                
                # 1. Look for Simple Fields (w:fldSimple)
                for fld in root.xpath("//w:fldSimple", namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                    instr = fld.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr")
                    if instr and "MERGEFIELD" in instr:
                        parts = instr.split()
                        if len(parts) >= 2:
                            placeholders.append(parts[parts.index("MERGEFIELD") + 1])
                
                # 2. Look for Complex Fields (w:instrText)
                for instr_text in root.xpath("//w:instrText", namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                    text = instr_text.text
                    if text and "MERGEFIELD" in text:
                        parts = text.split()
                        if len(parts) >= 2:
                            placeholders.append(parts[parts.index("MERGEFIELD") + 1])
                            
                # 3. Raw regex on XML
                raw_xml = xml_content.decode('utf-8', errors='ignore')
                extra_matches = re.findall(r"&#171;(.*?)&#187;", raw_xml)
                placeholders.extend(extra_matches)
    except Exception as e:
        print(f"Error: {e}")
        
    return list(set([p.strip() for p in placeholders if p.strip()]))

def test_final_logic():
    file_path = r"C:\Users\dpanc\Downloads\UK Telecoms.docx"
    with open(file_path, "rb") as f:
        content = f.read()

    print("Running Deep XML Scan...")
    placeholders = get_docx_placeholders_from_xml(content)
    print(f"Final Detected Placeholders: {placeholders}")
    
    if "CandidateID" in placeholders and "CandidateFullName" in placeholders:
        print("SUCCESS: Both CandidateID and CandidateFullName were found via Deep XML Scan!")
    else:
        print("FAILURE: Fields still missing.")

if __name__ == "__main__":
    test_final_logic()
