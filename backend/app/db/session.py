import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the .data directory exists
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.data"))
os.makedirs(DATA_DIR, exist_ok=True)

from app.config import settings
SQLALCHEMY_DATABASE_URL = settings.database_url

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    # Ensure tables exist (e.g. if they were dropped by clean_db.py while the server was running)
    try:
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
