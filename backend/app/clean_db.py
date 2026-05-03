import logging
from app.db.session import engine
from app.db.models import Base
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_database():
    logger.info("Connecting to RDS PostgreSQL to clean database...")
    try:
        # 1. Drop everything
        with engine.connect() as conn:
            # Disable triggers to avoid FK issues during drop (specific to Postgres)
            conn.execute(text("SET session_replication_role = 'replica';"))
            
            logger.info("Dropping all tables...")
            Base.metadata.drop_all(bind=engine)
            
            conn.execute(text("SET session_replication_role = 'origin';"))
            conn.commit()

        # 2. Recreate fresh
        logger.info("Recreating all tables from fresh schemas...")
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database cleaned and reset successfully!")
    except Exception as e:
        logger.error(f"Failed to clean database: {e}")
        raise

if __name__ == "__main__":
    clean_database()
