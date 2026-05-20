from app.db.session import engine
from app.db.models import Base
# Recreate all tables to ensure new columns are added (development only)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Database initialized with fresh schema")
