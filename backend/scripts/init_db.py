import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import engine
from app.db.models import Base

def init_db():
    print("Creating all tables from models...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    init_db()
