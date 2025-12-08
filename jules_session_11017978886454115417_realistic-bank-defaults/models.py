from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'cedente' or 'agente'
    
    # Relationships
    bank_configs = db.relationship('BankConfig', backref='user', lazy=True)

class BankConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    bank_type = db.Column(db.String(20), nullable=False) # 'santander' or 'bmp'
    agency = db.Column(db.String(10), nullable=True)
    account = db.Column(db.String(20), nullable=True)
    wallet = db.Column(db.String(5), nullable=True)
    convenio = db.Column(db.String(20), nullable=True)
    
    current_nosso_numero = db.Column(db.Integer, default=1)
    min_nosso_numero = db.Column(db.Integer, default=1)
    max_nosso_numero = db.Column(db.Integer, default=999999999)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    upload_type = db.Column(db.String(20), nullable=False) # 'nfe', 'cte', 'manual'
    file_path = db.Column(db.String(255), nullable=True) # Path to XML or PDF
    original_filename = db.Column(db.String(255), nullable=True)
    
    sacado_name = db.Column(db.String(200), nullable=False)
    sacado_doc = db.Column(db.String(20), nullable=False) # CPF/CNPJ
    
    amount = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    doc_number = db.Column(db.String(50), nullable=False) # Nota Number
    
    status = db.Column(db.String(20), default='pending') # pending, boleto_generated
    boleto_id = db.Column(db.Integer, db.ForeignKey('boleto.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Boleto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    sacado_name = db.Column(db.String(200), nullable=False)
    sacado_doc = db.Column(db.String(20), nullable=False)
    
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    
    nosso_numero = db.Column(db.String(20), nullable=False)
    digitable_line = db.Column(db.String(100), nullable=True)
    barcode = db.Column(db.String(100), nullable=True)
    
    bank = db.Column(db.String(50), nullable=False) # 'santander', 'bmp'
    
    status = db.Column(db.String(20), default='printed') # printed, selected, registered
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = db.relationship('User', backref=db.backref('boletos', lazy=True))
    
    # Relationship to invoices
    invoices = db.relationship('Invoice', backref='boleto', lazy=True)
