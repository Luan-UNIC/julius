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
Version: 3.0.0
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
    - 'admin': Can configure bank settings and user details
    """
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'cedente', 'agente', 'admin'

    # New Cedente Details
    razao_social = db.Column(db.String(200), nullable=True)
    cnpj = db.Column(db.String(20), nullable=True)  # Numbers only

    # Cedente Address
    address_street = db.Column(db.String(200), nullable=True)  # Logradouro
    address_number = db.Column(db.String(20), nullable=True)
    address_complement = db.Column(db.String(100), nullable=True)
    address_neighborhood = db.Column(db.String(100), nullable=True)  # Bairro
    address_city = db.Column(db.String(100), nullable=True)
    address_state = db.Column(db.String(2), nullable=True)  # UF
    address_zip = db.Column(db.String(10), nullable=True)  # CEP
    
    # Relationships
    bank_configs = db.relationship('BankConfig', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self) -> str:
        return f'<User {self.username} ({self.role})>'


class BankConfig(db.Model):
    """
    Bank configuration for cedente users.
    Stores bank-specific settings and nosso_numero sequence management.
    """
    __tablename__ = 'bank_config'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    bank_type = db.Column(db.String(20), nullable=False, index=True)  # 'santander' or 'bmp'
    agency = db.Column(db.String(10), nullable=True)
    account = db.Column(db.String(20), nullable=True)
    wallet = db.Column(db.String(5), nullable=True)  # Carteira
    convenio = db.Column(db.String(20), nullable=True)
    codigo_transmissao = db.Column(db.String(50), nullable=True) # Santander specific
    
    # Nosso Número management (atomic increment required)
    current_nosso_numero = db.Column(db.Integer, default=1, nullable=False)
    min_nosso_numero = db.Column(db.Integer, default=1, nullable=False)
    max_nosso_numero = db.Column(db.Integer, default=999999999, nullable=False)
    
    # Financial Instructions (Regras de Negocio)
    juros_percent = db.Column(db.Float, nullable=True) # Juros mensal %
    multa_percent = db.Column(db.Float, nullable=True) # Multa %
    desconto_value = db.Column(db.Float, nullable=True) # Valor ou %
    desconto_days = db.Column(db.Integer, nullable=True) # Dias ate vencimento
    protesto_dias = db.Column(db.Integer, nullable=True)
    baixa_dias = db.Column(db.Integer, nullable=True)

    # Bank activation status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f'<BankConfig user_id={self.user_id} bank={self.bank_type} active={self.is_active}>'


class Invoice(db.Model):
    """
    Invoice/Fiscal document model.
    Represents uploaded NFe, CTe, or manually entered invoices.
    """
    __tablename__ = 'invoice'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    upload_type = db.Column(db.String(20), nullable=False)  # 'nfe', 'cte', 'manual'
    file_path = db.Column(db.String(255), nullable=True)  # Path to XML or PDF
    original_filename = db.Column(db.String(255), nullable=True)
    
    sacado_name = db.Column(db.String(200), nullable=False)
    sacado_doc = db.Column(db.String(20), nullable=False, index=True)  # CPF/CNPJ
    
    # Sacado Address Details
    sacado_address = db.Column(db.String(200), nullable=True) # Logradouro + Numero
    sacado_neighborhood = db.Column(db.String(100), nullable=True)
    sacado_city = db.Column(db.String(100), nullable=True)
    sacado_state = db.Column(db.String(2), nullable=True)
    sacado_zip = db.Column(db.String(10), nullable=True)

    amount = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    doc_number = db.Column(db.String(50), nullable=False)
    
    especie = db.Column(db.String(10), default='DM', nullable=True) # DM, DS, etc.

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
