import sys
sys.path.append('backend')
from app.db.session import engine
from app.db.models import Base

# Create tables in the test db if needed
Base.metadata.create_all(bind=engine)
print("Tables created")
