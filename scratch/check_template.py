
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
import json

def check_template(template_id):
    db = SessionLocal()
    try:
        repo = SqlAlchemyTemplateRepository(db)
        template = repo.get_template(template_id)
        if not template:
            print(f"Template {template_id} NOT FOUND")
            return
        
        print(f"Template: {template.name}")
        print(f"Expected Fields: {template.expected_fields}")
        print(f"Manifest Type: {type(template.field_extraction_manifest)}")
        print(f"Manifest: {template.field_extraction_manifest}")
        
        if template.field_extraction_manifest:
            try:
                manifest = json.loads(template.field_extraction_manifest)
                print(f"Manifest length: {len(manifest)}")
            except:
                print("Manifest is not valid JSON")
    finally:
        db.close()

if __name__ == "__main__":
    check_template("6908972e-3363-4796-9f79-994b61b36952")
