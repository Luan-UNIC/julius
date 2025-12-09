"""
Database Migration Script - Version 2.1.0
==========================================

Adds new columns and tables:
1. BankConfig.sequencial_remessa
2. CNABFile table

Author: FIDC Development Team
"""

from app import app, db
from models import BankConfig, CNABFile
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_database():
    """Run database migrations."""
    with app.app_context():
        try:
            logger.info("Starting database migration v2.1.0...")
            
            # Check if sequencial_remessa column exists in bank_config
            with db.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT COUNT(*) FROM pragma_table_info('bank_config') "
                    "WHERE name='sequencial_remessa'"
                ))
                column_exists = result.scalar() > 0
                
                if not column_exists:
                    logger.info("Adding sequencial_remessa column to bank_config...")
                    conn.execute(text(
                        "ALTER TABLE bank_config ADD COLUMN sequencial_remessa INTEGER DEFAULT 1 NOT NULL"
                    ))
                    conn.commit()
                    logger.info("✓ Column sequencial_remessa added successfully")
                else:
                    logger.info("✓ Column sequencial_remessa already exists")
            
            # Create CNABFile table if it doesn't exist
            logger.info("Creating CNABFile table if not exists...")
            db.create_all()
            logger.info("✓ CNABFile table created successfully")
            
            logger.info("✅ Database migration completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            raise


if __name__ == '__main__':
    migrate_database()
