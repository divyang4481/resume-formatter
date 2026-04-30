import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Determine the database URL
if settings.database_url:
    SQLALCHEMY_DATABASE_URL = settings.database_url
    # For PostgreSQL or other DBs, check_same_thread is usually not needed/allowed
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    # Ensure the database directory exists for SQLite
    db_full_path = os.path.abspath(settings.sqlite_db_path)
    db_dir = os.path.dirname(db_full_path)
    os.makedirs(db_dir, exist_ok=True)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_full_path}"
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
