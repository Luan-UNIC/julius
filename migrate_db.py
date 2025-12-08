#!/usr/bin/env python3
"""
Database Migration Script for FIDC Middleware v3.0.0
======================================================

This script migrates the database to v3.0.0 schema.
Adds fields for User details (address/CNPJ), Invoice address, and Bank financial instructions.

Usage:
    python migrate_db.py
"""

import sqlite3
import os
from datetime import datetime

def migrate_database(db_path='instance/fidc.db'):
    """
    Migrate database to v3.0.0
    """
    
    if not os.path.exists(db_path):
        # Try checking root if not in instance
        if os.path.exists('fidc.db'):
            db_path = 'fidc.db'
        else:
            print(f"Error: Database file '{db_path}' not found!")
            return False
    
    # Backup database
    backup_path = f"{db_path}.backup_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"\nStarting migration to v3.0.0 on {db_path}...")
        
        # 1. Update User table
        print("1. Updating User table...")
        user_cols = [
            ("razao_social", "VARCHAR(200)"),
            ("cnpj", "VARCHAR(20)"),
            ("address_street", "VARCHAR(200)"),
            ("address_number", "VARCHAR(20)"),
            ("address_complement", "VARCHAR(100)"),
            ("address_neighborhood", "VARCHAR(100)"),
            ("address_city", "VARCHAR(100)"),
            ("address_state", "VARCHAR(2)"),
            ("address_zip", "VARCHAR(10)")
        ]
        for col_name, col_type in user_cols:
            try:
                cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
                print(f"   ✓ Added {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"   - {col_name} already exists")
                else:
                    raise

        # 2. Update BankConfig table
        print("2. Updating BankConfig table...")
        bank_cols = [
            ("codigo_transmissao", "VARCHAR(50)"),
            ("juros_percent", "FLOAT"),
            ("multa_percent", "FLOAT"),
            ("desconto_value", "FLOAT"),
            ("desconto_days", "INTEGER"),
            ("protesto_dias", "INTEGER"),
            ("baixa_dias", "INTEGER")
        ]
        for col_name, col_type in bank_cols:
            try:
                cursor.execute(f"ALTER TABLE bank_config ADD COLUMN {col_name} {col_type}")
                print(f"   ✓ Added {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"   - {col_name} already exists")
                else:
                    raise

        # 3. Update Invoice table
        print("3. Updating Invoice table...")
        inv_cols = [
            ("sacado_address", "VARCHAR(200)"),
            ("sacado_neighborhood", "VARCHAR(100)"),
            ("sacado_city", "VARCHAR(100)"),
            ("sacado_state", "VARCHAR(2)"),
            ("sacado_zip", "VARCHAR(10)"),
            ("especie", "VARCHAR(10) DEFAULT 'DM'")
        ]
        for col_name, col_type in inv_cols:
            try:
                cursor.execute(f"ALTER TABLE invoice ADD COLUMN {col_name} {col_type}")
                print(f"   ✓ Added {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"   - {col_name} already exists")
                else:
                    raise

        conn.commit()
        print("\n✓ Migration completed successfully!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Error during migration: {str(e)}")
        conn.rollback()
        conn.close()
        return False

if __name__ == '__main__':
    migrate_database()
