import sys
import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.schema import DropTable

# Add the app directory to the path so we can import models if needed
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

def clean_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found in environment.")
        return

    print(f"Connecting to {database_url.split('@')[-1]}...")
    engine = create_engine(database_url)
    metadata = MetaData()
    metadata.reflect(bind=engine)

    print(f"Found {len(metadata.tables)} tables. Dropping...")
    
    # We drop in reverse order of foreign keys
    metadata.drop_all(bind=engine)
    
    print("Database cleaned successfully.")

if __name__ == "__main__":
    clean_db()
