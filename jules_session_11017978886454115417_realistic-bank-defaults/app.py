from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Invoice, Boleto, BankConfig
from services import XmlParser, BoletoBuilder, CnabService
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask import send_file
import io
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fidc.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'cedente':
            return redirect(url_for('cedente_dashboard'))
        elif current_user.role == 'agente':
            return redirect(url_for('agente_dashboard'))
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
def cedente_dashboard():
    if current_user.role != 'cedente':
        return redirect(url_for('index'))
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).all()
    # Check if user has bank configs
    if not current_user.bank_configs:
         flash("Please configure your bank settings first.")
         return redirect(url_for('cedente_settings'))
    return render_template('cedente_dashboard.html', invoices=invoices)

@app.route('/cedente/settings', methods=['GET', 'POST'])
@login_required
def cedente_settings():
    if current_user.role != 'cedente':
        return redirect(url_for('index'))
    
    santander_config = BankConfig.query.filter_by(user_id=current_user.id, bank_type='santander').first()
    bmp_config = BankConfig.query.filter_by(user_id=current_user.id, bank_type='bmp').first()
    
    if request.method == 'POST':
        # Santander
        santander_config.agency = request.form.get('santander_agency')
        santander_config.account = request.form.get('santander_account')
        santander_config.wallet = request.form.get('santander_wallet')
        santander_config.convenio = request.form.get('santander_convenio')
        santander_config.min_nosso_numero = int(request.form.get('santander_min_nn'))
        santander_config.max_nosso_numero = int(request.form.get('santander_max_nn'))
        santander_config.current_nosso_numero = int(request.form.get('santander_current_nn'))
        
        # BMP
        bmp_config.agency = request.form.get('bmp_agency')
        bmp_config.account = request.form.get('bmp_account')
        bmp_config.wallet = request.form.get('bmp_wallet')
        bmp_config.convenio = request.form.get('bmp_convenio')
        bmp_config.min_nosso_numero = int(request.form.get('bmp_min_nn'))
        bmp_config.max_nosso_numero = int(request.form.get('bmp_max_nn'))
        bmp_config.current_nosso_numero = int(request.form.get('bmp_current_nn'))
        
        db.session.commit()
        flash("Settings updated successfully.")
        return redirect(url_for('cedente_settings'))

    return render_template('cedente_settings.html', santander=santander_config, bmp=bmp_config)

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
            invoice = Invoice(
                user_id=current_user.id,
                upload_type=file_type,
                file_path=filepath,
                original_filename=filename,
                sacado_name=data['sacado_name'],
                sacado_doc=data['sacado_doc'],
                amount=data['amount'],
                issue_date=data['issue_date'],
                doc_number=data['doc_number']
            )
            db.session.add(invoice)
            db.session.commit()
            flash('File uploaded and parsed successfully!')
            return redirect(url_for('cedente_dashboard'))
        else:
            flash('Failed to parse XML file. Ensure it is a valid NFe or CTe.')
            return redirect(url_for('upload_page'))

@app.route('/upload/manual', methods=['POST'])
@login_required
def manual_entry():
    sacado_name = request.form['sacado_name']
    sacado_doc = request.form['sacado_doc']
    amount = float(request.form['amount'])
    issue_date = datetime.strptime(request.form['issue_date'], '%Y-%m-%d').date()
    doc_number = request.form['doc_number']
    
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
    else:
        filepath = None
        filename = None

    invoice = Invoice(
        user_id=current_user.id,
        upload_type='manual',
        file_path=filepath,
        original_filename=filename,
        sacado_name=sacado_name,
        sacado_doc=sacado_doc,
        amount=amount,
        issue_date=issue_date,
        doc_number=doc_number
    )
    db.session.add(invoice)
    db.session.commit()
    flash('Manual entry saved successfully!')
    return redirect(url_for('cedente_dashboard'))

@app.route('/cedente/generate_boleto', methods=['POST'])
@login_required
def generate_boleto():
    invoice_ids = request.form.getlist('invoice_ids')
    target_bank = request.form.get('target_bank') # 'santander' or 'bmp'
    
    if not invoice_ids:
        flash('No invoices selected')
        return redirect(url_for('cedente_dashboard'))
    
    # Get Config
    bank_config = BankConfig.query.filter_by(user_id=current_user.id, bank_type=target_bank).first()
    if not bank_config:
        flash(f"Configuration for {target_bank} not found.")
        return redirect(url_for('cedente_dashboard'))
    
    invoices = Invoice.query.filter(Invoice.id.in_(invoice_ids)).all()
    
    # Group by Sacado Doc
    grouped = {}
    for inv in invoices:
        if inv.sacado_doc not in grouped:
            grouped[inv.sacado_doc] = []
        grouped[inv.sacado_doc].append(inv)
        
    generated_count = 0
    
    for doc, inv_list in grouped.items():
        # Validate Range
        if bank_config.current_nosso_numero > bank_config.max_nosso_numero:
             flash(f"Nosso Numero limit reached for {target_bank}. Increase max limit in settings.")
             break
             
        # Sum amount
        total_amount = sum(i.amount for i in inv_list)
        sacado_name = inv_list[0].sacado_name
        
        # Calculate Due Date (Standard 30 days or from input? Let's say +30 days from today)
        due_date = datetime.now().date() + timedelta(days=5)
        
        # Get Nosso Numero
        nosso_numero = bank_config.current_nosso_numero
        bank_config.current_nosso_numero += 1
        
        # Calculate Digits
        # Simplified for demo
        full_nosso_numero = f"{bank_config.wallet}{str(nosso_numero).zfill(11)}"
        if bank_config.bank_type == 'santander':
            bank_code_num = '033'
            formatted_nn = BoletoBuilder.calculate_santander_nosso_numero(nosso_numero)
        else:
            bank_code_num = 'BMP' # Mock BMP code? usually numeric like 274? BMP Money Plus is 341? No, BMP is 274 or similar. Let's stick to 'BMP' str for now unless strictly numeric needed.
            formatted_nn = str(nosso_numero)
            
        boleto = Boleto(
            user_id=current_user.id,
            sacado_name=sacado_name,
            sacado_doc=doc,
            amount=total_amount,
            due_date=due_date,
            nosso_numero=str(nosso_numero),
            bank=bank_code_num,
            digitable_line=f"{bank_code_num}99.{bank_config.agency} {bank_config.account} {formatted_nn} {total_amount}", # Mock
            barcode=f"{bank_code_num}9{total_amount}{formatted_nn}", # Mock
            status='printed'
        )
        db.session.add(boleto)
        db.session.commit() # Commit to get ID
        
        # Link invoices
        for inv in inv_list:
            inv.boleto_id = boleto.id
            inv.status = 'boleto_generated'
            
        # Generate PDF
        pdf_filename = f"boleto_{boleto.id}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        
        BoletoBuilder.generate_pdf({
            'bank_name': 'Banco Santander' if bank_config.bank_type == 'santander' else 'BMP MoneyPlus',
            'bank_code': bank_code_num,
            'digitable_line': boleto.digitable_line,
            'cedente_name': current_user.username,
            'due_date': boleto.due_date,
            'amount': boleto.amount,
            'sacado_name': boleto.sacado_name,
            'sacado_doc': boleto.sacado_doc,
            'barcode': boleto.barcode
        }, pdf_path)
        
        generated_count += 1
        
    db.session.commit()
    flash(f'{generated_count} Boletos generated successfully using {target_bank.upper()}!')
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
def agente_dashboard():
    if current_user.role != 'agente':
        return redirect(url_for('index'))
    boletos = Boleto.query.order_by(Boleto.created_at.desc()).all()
    return render_template('agente_dashboard.html', boletos=boletos)

@app.route('/agente/approve', methods=['POST'])
@login_required
def approve_boletos():
    if current_user.role != 'agente':
        return redirect(url_for('index'))
        
    boleto_ids = request.form.getlist('boleto_ids')
    if boleto_ids:
        boletos = Boleto.query.filter(Boleto.id.in_(boleto_ids)).all()
        for b in boletos:
            if b.status == 'printed':
                b.status = 'selected'
        db.session.commit()
        flash(f'{len(boletos)} Boletos approved/selected for Remessa.')
    
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/generate_remessa')
@login_required
def generate_remessa():
    if current_user.role != 'agente':
        return redirect(url_for('index'))
    
    # Get all selected boletos
    boletos = Boleto.query.filter_by(status='selected').all()
    if not boletos:
        flash('No boletos selected for remessa.')
        return redirect(url_for('agente_dashboard'))
    
    # For MVP, we assume all boletos belong to the same bank or we separate them.
    # We will grab the bank from the first boleto to decide (Santander vs BMP).
    # In a real system, we'd group by bank/cedente.
    # We will use the Cedente's bank config for generation.
    
    first_boleto = boletos[0]
    cedente = User.query.get(first_boleto.user_id)
    
    # Determine bank type based on the Boleto's bank code
    # This assumes the Boleto.bank field stores the code used during generation ('033' or 'BMP')
    
    if first_boleto.bank == '033': # Santander
        content = CnabService.generate_santander_240(boletos, cedente)
        filename = f"REMESSA_SANTANDER_{datetime.now().strftime('%Y%m%d%H%M')}.REM"
    else: # BMP (Defaulting to 400 for anything else)
        content = CnabService.generate_bmp_400(boletos, cedente)
        filename = f"REMESSA_BMP_{datetime.now().strftime('%Y%m%d%H%M')}.REM"
        
    # Update status
    for b in boletos:
        b.status = 'registered'
    db.session.commit()
    
    # Send file
    mem = io.BytesIO()
    mem.write(content.encode('utf-8')) # CNAB is typically ASCII/ANSI, but utf-8 is safe for now
    mem.seek(0)
    
    return send_file(
        mem,
        as_attachment=True,
        download_name=filename,
        mimetype='text/plain'
    )

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
        
        db.session.commit()
        print("Database initialized.")

if __name__ == '__main__':
    if not os.path.exists('fidc.db'):
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
