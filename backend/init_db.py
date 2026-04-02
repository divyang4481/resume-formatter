from app.db.session import engine
from app.db.models import Base

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Database tables created.")
