"""
FIDC Middleware - Database Models
==================================

SQLAlchemy models for the FIDC system.

Models:
- User: System users (cedente and agente roles)
- BankConfig: Bank-specific configuration for cedentes (with activation control)
- Invoice: Uploaded or manually entered invoices/fiscal documents (with soft delete)
- Boleto: Generated payment slips (boletos bancários) (with soft delete)
- TransactionHistory: Audit trail for all operations

Author: FIDC Development Team
Version: 2.0.0
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from typing import List

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    User model representing system users.
    
    Roles:
    - 'cedente': Can upload invoices and generate boletos
    - 'agente': Can approve boletos and generate CNAB remittance files
    """
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'cedente' or 'agente'
    
    # Relationships
    bank_configs = db.relationship('BankConfig', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self) -> str:
        return f'<User {self.username} ({self.role})>'


class BankConfig(db.Model):
    """
    Bank configuration for cedente users.
    Stores bank-specific settings and nosso_numero sequence management.
    
    Attributes:
        bank_type: 'santander' or 'bmp'
        agency: Bank agency code
        account: Account number (with or without check digit)
        wallet: Carteira code (e.g., '101' for Santander, '109' for BMP)
        convenio: Convenio/agreement code
        current_nosso_numero: Current sequential number for boletos
        min_nosso_numero: Minimum allowed nosso_numero
        max_nosso_numero: Maximum allowed nosso_numero
        is_active: Whether this bank is enabled for the cedente
    """
    __tablename__ = 'bank_config'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    bank_type = db.Column(db.String(20), nullable=False, index=True)  # 'santander' or 'bmp'
    agency = db.Column(db.String(10), nullable=True)
    account = db.Column(db.String(20), nullable=True)
    wallet = db.Column(db.String(5), nullable=True)  # Carteira
    convenio = db.Column(db.String(20), nullable=True)
    
    # Nosso Número management (atomic increment required)
    current_nosso_numero = db.Column(db.Integer, default=1, nullable=False)
    min_nosso_numero = db.Column(db.Integer, default=1, nullable=False)
    max_nosso_numero = db.Column(db.Integer, default=999999999, nullable=False)
    
    # Bank activation status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f'<BankConfig user_id={self.user_id} bank={self.bank_type} active={self.is_active}>'


class Invoice(db.Model):
    """
    Invoice/Fiscal document model.
    Represents uploaded NFe, CTe, or manually entered invoices.
    
    Attributes:
        upload_type: 'nfe', 'cte', or 'manual'
        file_path: Path to uploaded XML/PDF file
        sacado_name: Payer name
        sacado_doc: Payer CPF/CNPJ
        amount: Invoice amount in BRL
        issue_date: Invoice issue date
        doc_number: Invoice/document number
        status: 'pending' or 'boleto_generated'
        boleto_id: FK to generated Boleto (if any)
        deleted_at: Soft delete timestamp
        deleted_by: User who deleted this record
    """
    __tablename__ = 'invoice'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    upload_type = db.Column(db.String(20), nullable=False)  # 'nfe', 'cte', 'manual'
    file_path = db.Column(db.String(255), nullable=True)  # Path to XML or PDF
    original_filename = db.Column(db.String(255), nullable=True)
    
    sacado_name = db.Column(db.String(200), nullable=False)
    sacado_doc = db.Column(db.String(20), nullable=False, index=True)  # CPF/CNPJ
    
    amount = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    doc_number = db.Column(db.String(50), nullable=False)
    
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    boleto_id = db.Column(db.Integer, db.ForeignKey('boleto.id'), nullable=True, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Soft delete fields
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships - explicitly specify foreign_keys to avoid ambiguity
    cedente = db.relationship('User', foreign_keys=[user_id], backref=db.backref('invoices', lazy=True))
    deleted_by_user = db.relationship('User', foreign_keys=[deleted_by])
    
    def __repr__(self) -> str:
        return f'<Invoice {self.doc_number} - {self.sacado_name}>'


class Boleto(db.Model):
    """
    Boleto (Brazilian payment slip) model.
    Generated from one or more invoices, grouped by payer.
    
    Attributes:
        sacado_name: Payer name
        sacado_doc: Payer CPF/CNPJ
        amount: Total amount in BRL
        due_date: Payment due date
        nosso_numero: Sequential number assigned by bank
        digitable_line: 47-digit digitable line for manual entry
        barcode: 44-digit barcode (Febraban standard)
        bank: Bank code ('033' for Santander, '274' for BMP)
        status: 'pending', 'approved', 'cancelled', 'registered'
        deleted_at: Soft delete timestamp
        deleted_by: User who deleted this record
    """
    __tablename__ = 'boleto'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    sacado_name = db.Column(db.String(200), nullable=False)
    sacado_doc = db.Column(db.String(20), nullable=False, index=True)
    
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False, index=True)
    
    nosso_numero = db.Column(db.String(20), nullable=False, index=True)
    digitable_line = db.Column(db.String(100), nullable=True)
    barcode = db.Column(db.String(100), nullable=True)
    
    bank = db.Column(db.String(50), nullable=False, index=True)  # Bank code
    
    # Status: pending, approved, cancelled, registered
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Soft delete fields
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships - explicitly specify foreign_keys to avoid ambiguity
    cedente = db.relationship('User', foreign_keys=[user_id], backref=db.backref('boletos', lazy=True))
    deleted_by_user = db.relationship('User', foreign_keys=[deleted_by])
    invoices = db.relationship('Invoice', backref='boleto', lazy=True)
    
    def __repr__(self) -> str:
        return f'<Boleto {self.nosso_numero} - {self.sacado_name} - R$ {self.amount:.2f}>'


class TransactionHistory(db.Model):
    """
    Transaction history model for audit trail.
    Tracks all operations on boletos and invoices.
    
    Attributes:
        timestamp: When the action occurred
        user_id: User who performed the action
        entity_type: Type of entity ('boleto' or 'invoice')
        entity_id: ID of the affected entity
        action: Action performed ('created', 'updated', 'deleted', 'approved', 'cancelled', 'registered')
        details: JSON field with additional details (old values, new values, etc.)
        ip_address: IP address of the user (optional)
    """
    __tablename__ = 'transaction_history'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # 'boleto' or 'invoice'
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False, index=True)  # 'created', 'updated', 'deleted', etc.
    
    details = db.Column(db.Text, nullable=True)  # JSON string with additional details
    ip_address = db.Column(db.String(50), nullable=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('transaction_history', lazy=True))
    
    def __repr__(self) -> str:
        return f'<TransactionHistory {self.action} on {self.entity_type}#{self.entity_id} by user#{self.user_id}>'
