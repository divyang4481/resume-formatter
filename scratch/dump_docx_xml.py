import zipfile
import lxml.etree as ET

def dump_xml():
    file_path = r"C:\Users\dpanc\Downloads\UK Telecoms.docx"
    with zipfile.ZipFile(file_path, 'r') as z:
        xml_content = z.read('word/document.xml')
        
    # Prettify and print first 5000 chars to find the Candidate section
    root = ET.fromstring(xml_content)
    pretty_xml = ET.tostring(root, pretty_print=True).decode('utf-8')
    
    # Find "Candidate" and print surrounding context
    index = pretty_xml.find("Candidate")
    if index != -1:
        print(pretty_xml[index-500:index+2000])
    else:
        print("Candidate not found in XML.")

if __name__ == "__main__":
    dump_xml()
