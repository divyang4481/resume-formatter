import sys
import os
import asyncio
import json

# Add backend directory to path (parent of this script's directory)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.template_structure_extractor import TemplateStructureExtractor

async def main():
    if len(sys.argv) < 2:
        print("\nUsage: python verify_template.py <path_to_docx>")
        print("Example: python verify_template.py \"C:\\workspace\\CCCTTNS\\Hays_Resume_formater\\real_template\\UK Taxation.docx\"")
        return

    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"ERROR: File not found at {file_path}")
        return

    print(f"\n{'='*80}")
    print(f"HAYS TEMPLATE VERIFICATION: {os.path.basename(file_path)}")
    print(f"{'='*80}")

    with open(file_path, "rb") as f:
        content = f.read()

    extractor = TemplateStructureExtractor()
    struct = extractor.extract(content, os.path.basename(file_path))

    print(f"\n[1] LAYOUT STYLE: {struct.layout_style}")
    
    print(f"\n[2] DETECTED MARKERS: ({len(struct.detected_markers)})")
    # Group by repeated status
    for m in sorted(struct.detected_markers):
        repeat_info = " (REPEATED in doc)" if m in struct.repeated_markers else ""
        header_info = " [Header/Footer]" if m in struct.headers_footers_markers else ""
        print(f"  - {m}{repeat_info}{header_info}")

    if struct.table_label_value_pairs:
        print(f"\n[3] TABLE MAPPINGS (Label -> Marker):")
        for pair in struct.table_label_value_pairs:
            marker_info = f"MARKER: {pair.marker_text}" if pair.marker_text else "BLANK SLOT"
            print(f"  - '{pair.label}' -> {marker_info}")

    if struct.paste_zones:
        print(f"\n[4] PASTE ZONES (Section Headings):")
        for pz in struct.paste_zones:
            print(f"  - {pz}")

    if hasattr(struct, 'bullet_slots') and struct.bullet_slots:
        print(f"\n[4b] BULLET SLOTS (List Areas):")
        for bs in struct.bullet_slots:
            print(f"  - {bs}")

    if struct.all_headings:
        print(f"\n[4c] ALL DETECTED HEADINGS:")
        for h in struct.all_headings:
            print(f"  - {h}")

    if struct.table_loops:
        print(f"\n[5] TABLE LOOPS (Dynamic Tables):")
        for loop in struct.table_loops:
            # Check if this loop is linked to a heading
            linked_heading = next((h for h, l in struct.heading_to_loop.items() if l == loop.loop_name), None)
            link_info = f" (Linked to Heading: '{linked_heading}')" if linked_heading else ""
            print(f"  - {loop.loop_name}{link_info}: {loop.item_fields}")

    if hasattr(struct, 'heading_to_smart_pattern') and struct.heading_to_smart_pattern:
        print(f"\n[5b] SMART OBJECT PATTERNS (Visual Blueprints):")
        for h, pattern in struct.heading_to_smart_pattern.items():
            if pattern:
                print(f"  - {h}: {' -> '.join(pattern)}")
                
    if struct.instruction_blocks:
        print(f"\n[6] INSTRUCTION BLOCKS FOUND: {len(struct.instruction_blocks)}")

    print(f"\n[7] RAW PARAGRAPH DUMP (Top 100):")
    # We need to re-extract raw paragraphs for this dump
    from lxml import etree as ET
    import zipfile
    import io
    NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        if "word/document.xml" in z.namelist():
            root = ET.fromstring(z.read("word/document.xml"))
            paras = root.xpath("//w:p", namespaces=NS)
            for i, p in enumerate(paras[:100]):
                txt = "".join(t.text or "" for t in p.xpath(".//w:t", namespaces=NS)).strip()
                if txt:
                    # Show if it's a heading
                    style = "".join(s.get(f"{NS['w']}val") or "" for s in p.xpath(".//w:pStyle", namespaces=NS))
                    heading_mark = "[H] " if style.lower().startswith("heading") or (p.xpath(".//w:b", namespaces=NS) and len(txt) < 60) else "    "
                    print(f"  {i:02}: {heading_mark}{txt}")

    print(f"\n{'='*80}\nVERIFICATION COMPLETE\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())
