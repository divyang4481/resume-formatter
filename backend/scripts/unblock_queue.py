import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

script_path = Path(__file__).resolve()
backend_path = script_path.parent.parent
sys.path.insert(0, str(backend_path))
load_dotenv(backend_path / ".env.local")

from app.db.models import LocalQueueMessage
from app.config import Settings

def unblock_queue():
    settings = Settings()
    if not settings.database_url:
        settings.database_url = os.getenv('DATABASE_URL')
    
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Unblocking queue...")
    stuck_messages = session.query(LocalQueueMessage).filter(LocalQueueMessage.status == "processing").all()
    for msg in stuck_messages:
        print(f"Marking message {msg.id} (Job {msg.payload_json}) as pending to unblock.")
        msg.status = "pending"
    
    session.commit()
    print("Done.")
    session.close()

if __name__ == "__main__":
    unblock_queue()
