"""
FIDC Middleware - Flask Application
====================================

Main application file with routes, authentication, and business logic coordination.

Author: FIDC Development Team
Version: 2.0.0
"""

from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Invoice, Boleto, BankConfig, TransactionHistory
from services import XmlParser, BoletoBuilder, CnabService
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask import send_file
from typing import Optional, Tuple, List
from functools import wraps
import io
import os
import json
import csv
import traceback
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fidc.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper Functions ---

def log_transaction(entity_type: str, entity_id: int, action: str, details: dict = None):
    """
    Log a transaction to the audit trail.
    
    Args:
        entity_type: Type of entity ('boleto' or 'invoice')
        entity_id: ID of the entity
        action: Action performed ('created', 'updated', 'deleted', 'approved', 'cancelled', 'registered')
        details: Optional dictionary with additional details
    """
    try:
        history = TransactionHistory(
            user_id=current_user.id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details=json.dumps(details) if details else None,
            ip_address=request.remote_addr
        )
        db.session.add(history)
        db.session.flush()  # Flush but don't commit (caller will commit)
        logger.info(f"Transaction logged: {action} on {entity_type}#{entity_id} by user#{current_user.id}")
    except Exception as e:
        logger.error(f"Failed to log transaction: {str(e)}")

def get_active_invoices():
    """Get all non-deleted invoices for current user."""
    return Invoice.query.filter_by(
        user_id=current_user.id, 
        deleted_at=None
    ).order_by(Invoice.created_at.desc())

def get_active_boletos(user_id=None):
    """Get all non-deleted boletos, optionally filtered by user."""
    query = Boleto.query.filter_by(deleted_at=None)
    if user_id:
        query = query.filter_by(user_id=user_id)
    return query.order_by(Boleto.created_at.desc())

def get_active_bank_configs(user_id=None):
    """Get all active bank configs for a user."""
    if user_id is None:
        user_id = current_user.id
    return BankConfig.query.filter_by(user_id=user_id, is_active=True).all()

def validate_bank_selection(bank_type: str, user_id: int = None) -> Tuple[bool, str]:
    """
    Validate if a bank is active for the user.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if user_id is None:
        user_id = current_user.id
    
    config = BankConfig.query.filter_by(user_id=user_id, bank_type=bank_type).first()
    if not config:
        return False, f"Bank configuration for {bank_type} not found"
    
    if not config.is_active:
        return False, f"{bank_type.upper()} is currently disabled. Please enable it in settings."
    
    return True, ""

def get_bank_name(bank_code: str) -> str:
    """Get bank name from code."""
    bank_names = {
        '033': 'Santander',
        '274': 'BMP Money Plus'
    }
    return bank_names.get(bank_code, f'Bank {bank_code}')

def get_bank_type_from_code(bank_code: str) -> str:
    """Get bank type from code."""
    bank_map = {
        '033': 'santander',
        '274': 'bmp'
    }
    return bank_map.get(bank_code, 'unknown')

def format_currency(value: float) -> str:
    """Format currency as Brazilian Real."""
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def require_role(role: str):
    """Decorator to require specific user role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role != role:
                flash('Você não tem permissão para acessar esta página.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Routes ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'cedente':
            return redirect(url_for('cedente_dashboard'))
        elif current_user.role == 'agente':
            return redirect(url_for('agente_dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/cedente/dashboard')
@login_required
@require_role('cedente')
def cedente_dashboard():
    # Check if user has bank configs
    if not current_user.bank_configs:
         flash("Por favor, configure suas informações bancárias primeiro.", "warning")
         return redirect(url_for('cedente_settings'))
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    # Build query with soft delete filter
    query = get_active_invoices()
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                Invoice.sacado_name.ilike(f'%{search}%'),
                Invoice.sacado_doc.ilike(f'%{search}%'),
                Invoice.doc_number.ilike(f'%{search}%')
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Apply date filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Invoice.issue_date >= date_from_obj)
        except:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Invoice.issue_date <= date_to_obj)
        except:
            pass
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    invoices = pagination.items
    
    # Get active boletos for display
    boletos = get_active_boletos(current_user.id).all()
    
    # Get active bank configs
    active_banks = get_active_bank_configs()
    
    return render_template('cedente_dashboard.html', 
                         invoices=invoices,
                         boletos=boletos,
                         pagination=pagination,
                         active_banks=active_banks,
                         search=search,
                         status_filter=status_filter,
                         date_from=date_from,
                         date_to=date_to)

@app.route('/cedente/settings', methods=['GET'])
@login_required
@require_role('cedente')
def cedente_settings():
    """Read-only view of bank settings for Cedente."""
    santander_config = BankConfig.query.filter_by(user_id=current_user.id, bank_type='santander').first()
    bmp_config = BankConfig.query.filter_by(user_id=current_user.id, bank_type='bmp').first()
    
    flash("As configurações bancárias são gerenciadas pelo administrador.", "info")
    return render_template('cedente_settings.html', santander=santander_config, bmp=bmp_config, readonly=True)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_page():
    if current_user.role != 'cedente':
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/upload/file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        file.save(filepath)
        
        file_type, data = XmlParser.parse_file(filepath)
        
        if file_type and data:
            # Convert date to string for template
            data['issue_date'] = data['issue_date'].strftime('%Y-%m-%d')

            # Instead of saving immediately, redirect to review page
            return render_template('review_invoice.html',
                                 data=data,
                                 file_path=filepath,
                                 original_filename=filename,
                                 upload_type=file_type)
        else:
            flash('Failed to parse XML file. Ensure it is a valid NFe or CTe.')
            return redirect(url_for('upload_page'))

@app.route('/save_invoice', methods=['POST'])
@login_required
def save_invoice():
    """Final save after review or manual entry."""
    try:
        # Get data from form
        upload_type = request.form.get('upload_type', 'manual')
        file_path = request.form.get('file_path')
        original_filename = request.form.get('original_filename')

        # Handle file upload for manual entry if applicable
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(filepath)
            file_path = filepath
            original_filename = filename
            upload_type = 'manual'

        invoice = Invoice(
            user_id=current_user.id,
            upload_type=upload_type,
            file_path=file_path,
            original_filename=original_filename,

            # Payer Info
            sacado_name=request.form['sacado_name'],
            sacado_doc=request.form['sacado_doc'],
            sacado_address=request.form['sacado_address'],
            sacado_neighborhood=request.form['sacado_neighborhood'],
            sacado_city=request.form['sacado_city'],
            sacado_state=request.form['sacado_state'],
            sacado_zip=request.form['sacado_zip'],

            # Invoice Info
            amount=float(request.form['amount']),
            issue_date=datetime.strptime(request.form['issue_date'], '%Y-%m-%d').date(),
            doc_number=request.form['doc_number'],
            especie=request.form.get('especie', 'DM')
        )

        db.session.add(invoice)
        db.session.commit()

        flash('Fatura salva com sucesso!', 'success')
        return redirect(url_for('cedente_dashboard'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar fatura: {str(e)}', 'error')
        logger.error(f"Error saving invoice: {str(e)}")
        return redirect(url_for('upload_page'))

@app.route('/upload/manual', methods=['POST'])
@login_required
def manual_entry():
    """Legacy route redirection or direct handling."""
    # This might be called directly from upload.html manual tab
    # It acts same as save_invoice but from different form
    return save_invoice()

@app.route('/cedente/generate_boleto', methods=['POST'])
@login_required
@require_role('cedente')
def generate_boleto():
    """
    Generate boletos from selected invoices.
    Implements atomic nosso_numero increment with database locking.
    Calculates proper barcode and digitable line according to Febraban standards.
    """
    invoice_ids = request.form.getlist('invoice_ids')
    target_bank = request.form.get('target_bank')  # 'santander' or 'bmp'
    
    if not invoice_ids:
        flash('Nenhuma fatura selecionada', 'warning')
        return redirect(url_for('cedente_dashboard'))
    
    if not target_bank or target_bank not in ['santander', 'bmp']:
        flash('Seleção de banco inválida', 'error')
        return redirect(url_for('cedente_dashboard'))
    
    # Validate bank is active
    is_valid, error_msg = validate_bank_selection(target_bank)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('cedente_dashboard'))
    
    try:
        # Get Config
        bank_config = BankConfig.query.filter_by(
            user_id=current_user.id, 
            bank_type=target_bank
        ).with_for_update().first()  # Lock row for atomic update
        
        if not bank_config:
            flash(f"Configuration for {target_bank.upper()} not found. Please configure in settings.", 'error')
            return redirect(url_for('cedente_settings'))
        
        invoices = Invoice.query.filter(Invoice.id.in_(invoice_ids)).all()
        
        if not invoices:
            flash('No valid invoices found', 'error')
            return redirect(url_for('cedente_dashboard'))
        
        # Group by Sacado Doc
        grouped = {}
        for inv in invoices:
            if inv.sacado_doc not in grouped:
                grouped[inv.sacado_doc] = []
            grouped[inv.sacado_doc].append(inv)
        
        generated_count = 0
        
        for doc, inv_list in grouped.items():
            # Validate Range (atomic check)
            if bank_config.current_nosso_numero > bank_config.max_nosso_numero:
                flash(f"Nosso Numero limit reached for {target_bank.upper()}. Increase max limit in settings.", 'error')
                break
            
            # Atomic increment of nosso_numero
            nosso_numero = bank_config.current_nosso_numero
            bank_config.current_nosso_numero += 1
            
            # Sum amount
            total_amount = sum(i.amount for i in inv_list)
            sacado_name = inv_list[0].sacado_name
            
            # Calculate Due Date (5 days from now as default)
            due_date = datetime.now().date() + timedelta(days=5)
            
            # Bank-specific configuration
            if bank_config.bank_type == 'santander':
                bank_code = '033'
                bank_name = 'Banco Santander'
                carteira = bank_config.wallet or '101'
                formatted_nn = BoletoBuilder.calculate_santander_nosso_numero(nosso_numero, carteira)
            else:  # BMP
                bank_code = '274'
                bank_name = 'BMP Money Plus'
                carteira = bank_config.wallet or '109'
                # BMP uses nosso_numero + DV calculated separately
                from utils import calcular_dv_bmp
                dv = calcular_dv_bmp(carteira, nosso_numero)
                formatted_nn = f"{str(nosso_numero).zfill(11)}-{dv}"
            
            # Calculate proper barcode and digitable line
            account_clean = bank_config.account.split('-')[0] if '-' in bank_config.account else bank_config.account
            
            barcode, digitable_line = BoletoBuilder.calculate_barcode(
                bank_code=bank_code,
                currency_code='9',
                due_date=due_date,
                amount=total_amount,
                nosso_numero=str(nosso_numero).zfill(12),
                agency=bank_config.agency,
                account=account_clean,
                carteira=carteira
            )
            
            # Create Boleto record
            boleto = Boleto(
                user_id=current_user.id,
                sacado_name=sacado_name,
                sacado_doc=doc,
                amount=total_amount,
                due_date=due_date,
                nosso_numero=str(nosso_numero),
                bank=bank_code,
                digitable_line=digitable_line,
                barcode=barcode,
                status='printed'
            )
            db.session.add(boleto)
            db.session.flush()  # Get boleto ID without committing
            
            # Log transaction
            log_transaction('boleto', boleto.id, 'created', {
                'bank': bank_name,
                'amount': total_amount,
                'nosso_numero': str(nosso_numero),
                'sacado': sacado_name
            })
            
            # Link invoices
            for inv in inv_list:
                inv.boleto_id = boleto.id
                inv.status = 'boleto_generated'
                log_transaction('invoice', inv.id, 'updated', {
                    'status': 'boleto_generated',
                    'boleto_id': boleto.id
                })
            
            # Generate PDF
            pdf_filename = f"boleto_{boleto.id}.pdf"
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
            
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            
            BoletoBuilder.generate_pdf({
                'bank_name': bank_name,
                'bank_code': bank_code,
                'digitable_line': digitable_line,
                'cedente_name': current_user.username,
                'cedente_doc': '00.000.000/0000-00',  # TODO: Add to user model
                'cedente_address': 'Endereço não cadastrado',
                'agency_account': f"{bank_config.agency}/{account_clean}",
                'carteira': carteira,
                'due_date': due_date,
                'amount': total_amount,
                'sacado_name': sacado_name,
                'sacado_doc': doc,
                'sacado_address': 'Endereço não cadastrado',
                'barcode': barcode,
                'nosso_numero': formatted_nn,
                'doc_number': f"INV-{boleto.id}",
                'instructions': 'Não receber após o vencimento. Sujeito a multa e juros de mora.'
            }, pdf_path)
            
            generated_count += 1
        
        # Commit all changes atomically
        db.session.commit()
        flash(f'{generated_count} Boleto(s) generated successfully using {target_bank.upper()}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating boletos: {str(e)}', 'error')
        print(f"Error in generate_boleto: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('cedente_dashboard'))

@app.route('/download_boleto/<int:boleto_id>')
@login_required
def download_boleto(boleto_id):
    boleto = Boleto.query.get_or_404(boleto_id)
    filename = f"boleto_{boleto.id}.pdf"
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/view_lastro/<int:invoice_id>')
@login_required
def view_lastro(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if not invoice.file_path:
        return "No file attached", 404
    
    # Check permissions (Cedente owns it or Agente views it)
    if current_user.role == 'cedente' and invoice.user_id != current_user.id:
        return "Unauthorized", 403
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(invoice.file_path))

@app.route('/agente/dashboard')
@login_required
@require_role('agente')
def agente_dashboard():
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    bank_filter = request.args.get('bank', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    # Build query with soft delete filter
    query = get_active_boletos()
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                Boleto.sacado_name.ilike(f'%{search}%'),
                Boleto.sacado_doc.ilike(f'%{search}%'),
                Boleto.nosso_numero.ilike(f'%{search}%')
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Apply bank filter
    if bank_filter:
        query = query.filter_by(bank=bank_filter)
    
    # Apply date filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Boleto.due_date >= date_from_obj)
        except:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Boleto.due_date <= date_to_obj)
        except:
            pass
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    boletos = pagination.items
    
    # Group boletos by bank for statistics
    boletos_by_bank = {}
    for boleto in get_active_boletos().all():
        bank_code = boleto.bank
        bank_name = get_bank_name(bank_code)
        if bank_name not in boletos_by_bank:
            boletos_by_bank[bank_name] = {
                'code': bank_code,
                'count': 0,
                'total_value': 0,
                'pending': 0,
                'approved': 0,
                'registered': 0
            }
        boletos_by_bank[bank_name]['count'] += 1
        boletos_by_bank[bank_name]['total_value'] += boleto.amount
        boletos_by_bank[bank_name][boleto.status] = boletos_by_bank[bank_name].get(boleto.status, 0) + 1
    
    return render_template('agente_dashboard.html', 
                         boletos=boletos,
                         pagination=pagination,
                         boletos_by_bank=boletos_by_bank,
                         search=search,
                         status_filter=status_filter,
                         bank_filter=bank_filter,
                         date_from=date_from,
                         date_to=date_to,
                         get_bank_name=get_bank_name)

@app.route('/agente/approve', methods=['POST'])
@login_required
@require_role('agente')
def approve_boletos():
    boleto_ids = request.form.getlist('boleto_ids')
    if not boleto_ids:
        flash('Nenhum boleto selecionado.', 'warning')
        return redirect(url_for('agente_dashboard'))
    
    try:
        boletos = get_active_boletos().filter(Boleto.id.in_(boleto_ids)).all()
        approved_count = 0
        for b in boletos:
            if b.status in ['pending', 'printed']:
                old_status = b.status
                b.status = 'approved'
                log_transaction('boleto', b.id, 'approved', {
                    'old_status': old_status,
                    'new_status': 'approved',
                    'nosso_numero': b.nosso_numero
                })
                approved_count += 1
        
        db.session.commit()
        flash(f'{approved_count} boleto(s) aprovado(s) para remessa.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar boletos: {str(e)}', 'error')
        logger.error(f"Error approving boletos: {str(e)}")
    
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/generate_remessa')
@login_required
@require_role('agente')
def generate_remessa():
    """
    Generate CNAB remittance file for all approved boletos (all banks mixed).
    DEPRECATED: Use /agente/generate_remessa/<bank_code> instead for bank-specific files.
    """
    # Get all approved boletos
    boletos = get_active_boletos().filter_by(status='approved').all()
    if not boletos:
        flash('Nenhum boleto aprovado para remessa.', 'warning')
        return redirect(url_for('agente_dashboard'))
    
    # Redirect to bank-specific generation if only one bank
    banks = set(b.bank for b in boletos)
    if len(banks) == 1:
        return redirect(url_for('generate_remessa_by_bank', bank_code=list(banks)[0]))
    
    # If multiple banks, show error and ask to generate separately
    flash(f'Existem boletos de {len(banks)} bancos diferentes. Por favor, gere arquivos separados por banco.', 'warning')
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/generate_remessa/<bank_code>')
@login_required
@require_role('agente')
def generate_remessa_by_bank(bank_code):
    """
    Generate CNAB remittance file for approved boletos of a specific bank.
    This is the recommended way to generate remittance files.
    """
    # Get all approved boletos for this bank
    boletos = get_active_boletos().filter_by(status='approved', bank=bank_code).all()
    if not boletos:
        flash(f'Nenhum boleto aprovado para {get_bank_name(bank_code)}.', 'warning')
        return redirect(url_for('agente_dashboard'))
    
    try:
        # Group boletos by cedente (all same bank already)
        grouped = {}
        for boleto in boletos:
            cedente_id = boleto.user_id
            if cedente_id not in grouped:
                grouped[cedente_id] = []
            grouped[cedente_id].append(boleto)
        
        # If multiple cedentes, generate one file per cedente
        # For now, generate file for first cedente (can be extended to generate multiple files)
        if len(grouped) > 1:
            flash(f'Atenção: {len(grouped)} cedentes diferentes detectados. Gerando arquivo para o primeiro cedente apenas.', 'warning')
        
        # Get first group
        cedente_id, boleto_group = list(grouped.items())[0]
        
        # Get cedente (beneficiary who owns these boletos)
        cedente = User.query.get(cedente_id)
        if not cedente:
            flash('Cedente não encontrado para os boletos selecionados', 'error')
            return redirect(url_for('agente_dashboard'))
        
        # Determine bank type and generate appropriate file
        bank_name = get_bank_name(bank_code)
        if bank_code == '033':  # Santander
            content = CnabService.generate_santander_240(boleto_group, cedente)
            cnab_type = "CNAB 240"
        elif bank_code == '274':  # BMP
            content = CnabService.generate_bmp_400(boleto_group, cedente)
            cnab_type = "CNAB 400"
        else:
            flash(f'Código de banco desconhecido: {bank_code}', 'error')
            return redirect(url_for('agente_dashboard'))
        
        # Filename format: CB{DDMM}{SEQ}.REM (Cobrança Bancária + Date + Sequence)
        seq = str(len(boleto_group)).zfill(4)
        filename = f"CB{datetime.now().strftime('%d%m')}{seq}.REM"
        
        # Update boleto status and log transactions
        for boleto in boleto_group:
            old_status = boleto.status
            boleto.status = 'registered'
            log_transaction('boleto', boleto.id, 'registered', {
                'old_status': old_status,
                'new_status': 'registered',
                'bank': bank_name,
                'filename': filename
            })
        
        db.session.commit()
        
        flash(f'Arquivo de remessa gerado com sucesso para {len(boleto_group)} boleto(s) - {bank_name} {cnab_type}', 'success')
        logger.info(f"Remittance file {filename} generated for {len(boleto_group)} boletos by user {current_user.id}")
        
        # Send file
        mem = io.BytesIO()
        # CNAB files should use Windows line endings (CRLF) and ISO-8859-1 encoding
        mem.write(content.encode('iso-8859-1', errors='replace'))
        mem.seek(0)
        
        return send_file(
            mem,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao gerar arquivo de remessa: {str(e)}', 'error')
        logger.error(f"Error in generate_remessa_by_bank: {str(e)}\n{traceback.format_exc()}")
        return redirect(url_for('agente_dashboard'))

# --- Delete/Cancel Routes ---

@app.route('/cedente/delete_invoice/<int:invoice_id>', methods=['POST'])
@login_required
@require_role('cedente')
def delete_invoice(invoice_id):
    """Soft delete an invoice."""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # Check ownership
        if invoice.user_id != current_user.id:
            flash('Acesso não autorizado.', 'error')
            return redirect(url_for('cedente_dashboard'))
        
        # Check if already deleted
        if invoice.deleted_at:
            flash('Fatura já foi excluída.', 'warning')
            return redirect(url_for('cedente_dashboard'))
        
        # Check if has boleto
        if invoice.boleto_id:
            flash('Não é possível excluir fatura vinculada a um boleto. Cancele o boleto primeiro.', 'error')
            return redirect(url_for('cedente_dashboard'))
        
        # Soft delete
        invoice.deleted_at = datetime.utcnow()
        invoice.deleted_by = current_user.id
        
        log_transaction('invoice', invoice.id, 'deleted', {
            'doc_number': invoice.doc_number,
            'sacado': invoice.sacado_name
        })
        
        db.session.commit()
        flash('Fatura excluída com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir fatura: {str(e)}', 'error')
        logger.error(f"Error deleting invoice {invoice_id}: {str(e)}")
    
    return redirect(url_for('cedente_dashboard'))

@app.route('/cedente/cancel_boleto/<int:boleto_id>', methods=['POST'])
@login_required
@require_role('cedente')
def cancel_boleto(boleto_id):
    """Cancel a boleto (soft delete)."""
    try:
        boleto = Boleto.query.get_or_404(boleto_id)
        
        # Check ownership
        if boleto.user_id != current_user.id:
            flash('Acesso não autorizado.', 'error')
            return redirect(url_for('cedente_dashboard'))
        
        # Check if already deleted
        if boleto.deleted_at:
            flash('Boleto já foi cancelado.', 'warning')
            return redirect(url_for('cedente_dashboard'))
        
        # Check status - can only cancel pending or approved boletos
        if boleto.status == 'registered':
            flash('Não é possível cancelar boleto já registrado no banco.', 'error')
            return redirect(url_for('cedente_dashboard'))
        
        # Soft delete and update status
        old_status = boleto.status
        boleto.deleted_at = datetime.utcnow()
        boleto.deleted_by = current_user.id
        boleto.status = 'cancelled'
        
        # Unlink invoices
        for invoice in boleto.invoices:
            invoice.boleto_id = None
            invoice.status = 'pending'
        
        log_transaction('boleto', boleto.id, 'cancelled', {
            'old_status': old_status,
            'nosso_numero': boleto.nosso_numero,
            'amount': boleto.amount
        })
        
        db.session.commit()
        flash('Boleto cancelado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cancelar boleto: {str(e)}', 'error')
        logger.error(f"Error cancelling boleto {boleto_id}: {str(e)}")
    
    return redirect(url_for('cedente_dashboard'))

@app.route('/agente/cancel_boleto/<int:boleto_id>', methods=['POST'])
@login_required
@require_role('agente')
def agente_cancel_boleto(boleto_id):
    """Agent cancels a boleto (soft delete with more permissions)."""
    try:
        boleto = Boleto.query.get_or_404(boleto_id)
        
        # Check if already deleted
        if boleto.deleted_at:
            flash('Boleto já foi cancelado.', 'warning')
            return redirect(url_for('agente_dashboard'))
        
        # Agent can cancel any status except registered
        if boleto.status == 'registered':
            flash('Não é possível cancelar boleto já registrado no banco.', 'error')
            return redirect(url_for('agente_dashboard'))
        
        # Soft delete and update status
        old_status = boleto.status
        boleto.deleted_at = datetime.utcnow()
        boleto.deleted_by = current_user.id
        boleto.status = 'cancelled'
        
        # Unlink invoices
        for invoice in boleto.invoices:
            invoice.boleto_id = None
            invoice.status = 'pending'
        
        log_transaction('boleto', boleto.id, 'cancelled', {
            'old_status': old_status,
            'nosso_numero': boleto.nosso_numero,
            'amount': boleto.amount,
            'cancelled_by_agent': True
        })
        
        db.session.commit()
        flash('Boleto cancelado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cancelar boleto: {str(e)}', 'error')
        logger.error(f"Error cancelling boleto {boleto_id}: {str(e)}")
    
    return redirect(url_for('agente_dashboard'))

# --- Transaction History Routes ---

@app.route('/history')
@login_required
def transaction_history():
    """View transaction history."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    entity_filter = request.args.get('entity', '').strip()
    action_filter = request.args.get('action', '').strip()
    
    # Build query
    if current_user.role == 'cedente':
        # Cedentes see only their own transactions
        query = TransactionHistory.query.filter_by(user_id=current_user.id)
    else:
        # Agentes see all transactions
        query = TransactionHistory.query
    
    # Apply filters
    if entity_filter:
        query = query.filter_by(entity_type=entity_filter)
    
    if action_filter:
        query = query.filter_by(action=action_filter)
    
    # Order by newest first
    query = query.order_by(TransactionHistory.timestamp.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    history = pagination.items
    
    return render_template('transaction_history.html',
                         history=history,
                         pagination=pagination,
                         entity_filter=entity_filter,
                         action_filter=action_filter)

@app.route('/export/invoices')
@login_required
@require_role('cedente')
def export_invoices_csv():
    """Export invoices to CSV."""
    try:
        invoices = get_active_invoices().all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Tipo', 'Sacado', 'CPF/CNPJ', 'Valor', 'Data Emissão', 'Nº Documento', 'Status', 'Criado em'])
        
        # Write data
        for inv in invoices:
            writer.writerow([
                inv.id,
                inv.upload_type,
                inv.sacado_name,
                inv.sacado_doc,
                inv.amount,
                inv.issue_date.strftime('%d/%m/%Y'),
                inv.doc_number,
                inv.status,
                inv.created_at.strftime('%d/%m/%Y %H:%M')
            ])
        
        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=faturas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        logger.info(f"User {current_user.id} exported {len(invoices)} invoices to CSV")
        return response
    except Exception as e:
        flash(f'Erro ao exportar: {str(e)}', 'error')
        logger.error(f"Error exporting invoices: {str(e)}")
        return redirect(url_for('cedente_dashboard'))

@app.route('/export/boletos')
@login_required
def export_boletos_csv():
    """Export boletos to CSV."""
    try:
        if current_user.role == 'cedente':
            boletos = get_active_boletos(current_user.id).all()
        else:
            boletos = get_active_boletos().all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Nosso Número', 'Banco', 'Sacado', 'CPF/CNPJ', 'Valor', 'Vencimento', 'Status', 'Criado em'])
        
        # Write data
        for boleto in boletos:
            writer.writerow([
                boleto.id,
                boleto.nosso_numero,
                get_bank_name(boleto.bank),
                boleto.sacado_name,
                boleto.sacado_doc,
                boleto.amount,
                boleto.due_date.strftime('%d/%m/%Y'),
                boleto.status,
                boleto.created_at.strftime('%d/%m/%Y %H:%M')
            ])
        
        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=boletos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        logger.info(f"User {current_user.id} exported {len(boletos)} boletos to CSV")
        return response
    except Exception as e:
        flash(f'Erro ao exportar: {str(e)}', 'error')
        logger.error(f"Error exporting boletos: {str(e)}")
        return redirect(url_for('cedente_dashboard' if current_user.role == 'cedente' else 'agente_dashboard'))

# --- Admin Routes ---

@app.route('/admin/dashboard')
@login_required
@require_role('admin')
def admin_dashboard():
    users = User.query.filter(User.role != 'admin').all()
    return render_template('admin_dashboard.html', users=users)

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@require_role('admin')
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    santander_config = BankConfig.query.filter_by(user_id=user.id, bank_type='santander').first()
    bmp_config = BankConfig.query.filter_by(user_id=user.id, bank_type='bmp').first()

    if request.method == 'POST':
        try:
            # User Details
            user.razao_social = request.form.get('razao_social')
            user.cnpj = request.form.get('cnpj')
            user.address_street = request.form.get('address_street')
            user.address_number = request.form.get('address_number')
            user.address_complement = request.form.get('address_complement')
            user.address_neighborhood = request.form.get('address_neighborhood')
            user.address_city = request.form.get('address_city')
            user.address_state = request.form.get('address_state')
            user.address_zip = request.form.get('address_zip')

            # Santander Config
            if santander_config:
                santander_config.agency = request.form.get('santander_agency')
                santander_config.account = request.form.get('santander_account')
                santander_config.wallet = request.form.get('santander_wallet')
                santander_config.convenio = request.form.get('santander_convenio')
                santander_config.codigo_transmissao = request.form.get('santander_codigo_transmissao')
                santander_config.min_nosso_numero = int(request.form.get('santander_min_nn') or 0)
                santander_config.max_nosso_numero = int(request.form.get('santander_max_nn') or 999999999)
                santander_config.current_nosso_numero = int(request.form.get('santander_current_nn') or 1)

                santander_config.juros_percent = float(request.form.get('santander_juros') or 0)
                santander_config.multa_percent = float(request.form.get('santander_multa') or 0)
                santander_config.protesto_dias = int(request.form.get('santander_protesto') or 0)
                santander_config.baixa_dias = int(request.form.get('santander_baixa') or 0)

                santander_config.is_active = request.form.get('santander_active') == 'on'

            # BMP Config
            if bmp_config:
                bmp_config.agency = request.form.get('bmp_agency')
                bmp_config.account = request.form.get('bmp_account')
                bmp_config.wallet = request.form.get('bmp_wallet')
                bmp_config.convenio = request.form.get('bmp_convenio')
                bmp_config.min_nosso_numero = int(request.form.get('bmp_min_nn') or 0)
                bmp_config.max_nosso_numero = int(request.form.get('bmp_max_nn') or 999999999)
                bmp_config.current_nosso_numero = int(request.form.get('bmp_current_nn') or 1)

                bmp_config.juros_percent = float(request.form.get('bmp_juros') or 0)
                bmp_config.multa_percent = float(request.form.get('bmp_multa') or 0)
                bmp_config.protesto_dias = int(request.form.get('bmp_protesto') or 0)
                bmp_config.baixa_dias = int(request.form.get('bmp_baixa') or 0)

                bmp_config.is_active = request.form.get('bmp_active') == 'on'

            db.session.commit()
            flash('Usuário e configurações atualizados com sucesso.', 'success')
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {str(e)}', 'error')
            logger.error(f"Error updating user {user_id}: {str(e)}")

    return render_template('admin_edit_user.html', user=user, santander=santander_config, bmp=bmp_config)


# --- CLI to create DB ---
def init_db():
    with app.app_context():
        db.create_all()
        # Create default users if not exist
        if not User.query.filter_by(username='cedente').first():
            cedente = User(
                username='cedente', 
                password_hash=generate_password_hash('cedente'), 
                role='cedente'
            )
            db.session.add(cedente)
            db.session.commit()
            
            # Add Default Bank Configs
            # Santander (FIDC) - Realistic Defaults
            conf_santander = BankConfig(
                user_id=cedente.id,
                bank_type='santander',
                agency='3421',       # 4 digits
                account='13000456-7', # 8 digits + dash
                wallet='101',
                convenio='3421130',  # Typically related to agency/account
                current_nosso_numero=1000000, # Start higher
                min_nosso_numero=1000000,
                max_nosso_numero=9999999
            )
            # BMP (Escrow) - Realistic Defaults
            conf_bmp = BankConfig(
                user_id=cedente.id,
                bank_type='bmp',
                agency='0001',
                account='22345-1',
                wallet='109',
                convenio='102030',
                current_nosso_numero=2000000,
                min_nosso_numero=2000000,
                max_nosso_numero=8999999
            )
            db.session.add(conf_santander)
            db.session.add(conf_bmp)
        
        if not User.query.filter_by(username='agente').first():
            agente = User(
                username='agente', 
                password_hash=generate_password_hash('agente'), 
                role='agente'
            )
            db.session.add(agente)

        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                role='admin'
            )
            db.session.add(admin)
        
        db.session.commit()
        print("Database initialized.")

if __name__ == '__main__':
    if not os.path.exists('fidc.db'):
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
