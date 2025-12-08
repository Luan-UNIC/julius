#!/usr/bin/env python3
"""
Database Migration Script for FIDC Middleware v2.0.0
======================================================

This script migrates an existing v1.0.0 database to v2.0.0 schema.
Adds new fields for soft delete, transaction history, and bank activation.

Usage:
    python migrate_db.py

IMPORTANT: Backup your database before running this script!
"""

import sqlite3
import os
from datetime import datetime

def migrate_database(db_path='fidc.db'):
    """
    Migrate database from v1.0.0 to v2.0.0
    
    Changes:
    - Add is_active field to bank_config table
    - Add deleted_at and deleted_by fields to invoice table
    - Add deleted_at and deleted_by fields to boleto table
    - Update boleto status values (printed -> pending, selected -> approved)
    - Create transaction_history table
    """
    
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found!")
        print("If you're setting up a new installation, just run the application normally.")
        return False
    
    # Backup database
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print("✓ Backup created successfully")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n" + "="*60)
        print("Starting database migration to v2.0.0")
        print("="*60 + "\n")
        
        # Check if migration already applied
        cursor.execute("PRAGMA table_info(bank_config)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_active' in columns:
            print("⚠ Migration appears to have been already applied.")
            response = input("Do you want to continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                conn.close()
                return False
        
        # 1. Add is_active field to bank_config table
        print("1. Adding is_active field to bank_config table...")
        try:
            cursor.execute("""
                ALTER TABLE bank_config 
                ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_bank_config_is_active ON bank_config (is_active)")
            print("   ✓ Added is_active field")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("   - is_active field already exists, skipping")
            else:
                raise
        
        # 2. Add deleted_at and deleted_by fields to invoice table
        print("\n2. Adding soft delete fields to invoice table...")
        try:
            cursor.execute("""
                ALTER TABLE invoice 
                ADD COLUMN deleted_at DATETIME
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_invoice_deleted_at ON invoice (deleted_at)")
            print("   ✓ Added deleted_at field")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("   - deleted_at field already exists, skipping")
            else:
                raise
        
        try:
            cursor.execute("""
                ALTER TABLE invoice 
                ADD COLUMN deleted_by INTEGER REFERENCES user(id)
            """)
            print("   ✓ Added deleted_by field")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("   - deleted_by field already exists, skipping")
            else:
                raise
        
        # 3. Add deleted_at and deleted_by fields to boleto table
        print("\n3. Adding soft delete fields to boleto table...")
        try:
            cursor.execute("""
                ALTER TABLE boleto 
                ADD COLUMN deleted_at DATETIME
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_boleto_deleted_at ON boleto (deleted_at)")
            print("   ✓ Added deleted_at field")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("   - deleted_at field already exists, skipping")
            else:
                raise
        
        try:
            cursor.execute("""
                ALTER TABLE boleto 
                ADD COLUMN deleted_by INTEGER REFERENCES user(id)
            """)
            print("   ✓ Added deleted_by field")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("   - deleted_by field already exists, skipping")
            else:
                raise
        
        # 4. Update boleto status values
        print("\n4. Updating boleto status values...")
        cursor.execute("UPDATE boleto SET status = 'pending' WHERE status = 'printed'")
        printed_count = cursor.rowcount
        cursor.execute("UPDATE boleto SET status = 'approved' WHERE status = 'selected'")
        selected_count = cursor.rowcount
        print(f"   ✓ Updated {printed_count} 'printed' -> 'pending'")
        print(f"   ✓ Updated {selected_count} 'selected' -> 'approved'")
        
        # 5. Create transaction_history table
        print("\n5. Creating transaction_history table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                user_id INTEGER NOT NULL,
                entity_type VARCHAR(20) NOT NULL,
                entity_id INTEGER NOT NULL,
                action VARCHAR(20) NOT NULL,
                details TEXT,
                ip_address VARCHAR(50),
                FOREIGN KEY (user_id) REFERENCES user(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_transaction_history_timestamp ON transaction_history (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_transaction_history_user_id ON transaction_history (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_transaction_history_entity_type ON transaction_history (entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_transaction_history_entity_id ON transaction_history (entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_transaction_history_action ON transaction_history (action)")
        print("   ✓ Created transaction_history table with indexes")
        
        # Commit changes
        conn.commit()
        
        print("\n" + "="*60)
        print("✓ Migration completed successfully!")
        print("="*60)
        print(f"\nBackup saved at: {backup_path}")
        print("You can now run the application with the updated schema.")
        print("\nChanges applied:")
        print("  - Added bank activation control (is_active)")
        print("  - Added soft delete support for invoices and boletos")
        print("  - Updated boleto status values")
        print("  - Created transaction history audit table")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Error during migration: {str(e)}")
        print(f"Database has been backed up at: {backup_path}")
        print("You can restore it if needed.")
        conn.rollback()
        conn.close()
        return False

if __name__ == '__main__':
    print("FIDC Middleware Database Migration Tool")
    print("========================================\n")
    
    db_path = input("Enter database path (default: fidc.db): ").strip() or 'fidc.db'
    
    print(f"\n⚠ WARNING: This will modify the database at: {db_path}")
    print("A backup will be created automatically before migration.")
    response = input("\nDo you want to proceed? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        success = migrate_database(db_path)
        if success:
            print("\n✓ All done! You can now start the application.")
        else:
            print("\n✗ Migration failed or was cancelled.")
    else:
        print("\nMigration cancelled.")
