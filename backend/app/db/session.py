import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the .data directory exists
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.data"))
os.makedirs(DATA_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'app.db')}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
