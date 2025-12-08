# FIDC Middleware System

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.12-green)
![License](https://img.shields.io/badge/license-MIT-orange)

A complete FIDC (Fundo de Investimento em Direitos Creditórios) middleware system for processing invoices and generating boletos (Brazilian payment slips) with CNAB remittance files for bank submission.

## 📋 Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## ✨ Features

### Core Capabilities

- **Multi-Bank Support**: Santander (CNAB 240) and BMP Money Plus (CNAB 400)
- **Role-Based Access Control**: 
  - **Cedente**: Upload invoices, generate boletos
  - **Agente**: Approve boletos, generate CNAB remittance files
- **Invoice Processing**: 
  - NFe (Nota Fiscal Eletrônica) XML parsing
  - CTe (Conhecimento de Transporte Eletrônico) XML parsing
  - Manual invoice entry
- **Boleto Generation**: 
  - Febraban-compliant barcodes (Interleaved 2 of 5)
  - Digitable lines (47 digits)
  - Professional PDF layout
  - Automatic nosso_numero assignment
- **CNAB File Generation**: 
  - Santander CNAB 240 (hierarchical structure with segments)
  - BMP CNAB 400 (flat structure)
  - Proper encoding (ISO-8859-1) and line endings (CRLF)
- **Data Integrity**: 
  - Atomic nosso_numero increment (database-level locking)
  - Transaction-safe operations
  - Race condition prevention

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         FIDC Middleware                       │
├─────────────────┬───────────────────────┬────────────────────┤
│   Cedente UI    │      Agente UI        │    Database        │
│  (Invoice Mgmt) │   (Approval/CNAB)     │    (SQLite)        │
├─────────────────┴───────────────────────┴────────────────────┤
│                    Flask Application (app.py)                 │
├───────────────────────────────────────────────────────────────┤
│              Business Logic Layer (services.py)               │
│  ┌──────────────┬─────────────────┬───────────────────────┐  │
│  │ CnabService  │ BoletoBuilder   │   XmlParser           │  │
│  │ (CNAB 240/400)│ (PDF + Barcode) │  (NFe/CTe)            │  │
│  └──────────────┴─────────────────┴───────────────────────┘  │
├───────────────────────────────────────────────────────────────┤
│                   Data Layer (models.py)                      │
│  ┌──────┬─────────────┬─────────┬────────┐                   │
│  │ User │ BankConfig  │ Invoice │ Boleto │                   │
│  └──────┴─────────────┴─────────┴────────┘                   │
└───────────────────────────────────────────────────────────────┘
```

### Workflow

1. **Cedente** uploads invoices (XML) or enters manually
2. System parses and extracts payer information
3. **Cedente** selects invoices and generates boletos
4. System creates PDF boletos with barcodes and assigns nosso_numero
5. **Agente** reviews boletos and linked invoices (lastros)
6. **Agente** approves boletos for remittance
7. System generates CNAB file for bank submission
8. **Agente** submits CNAB file to bank portal

---

## 🛠️ Technology Stack

- **Backend**: Python 3.12, Flask 2.x
- **Database**: SQLite (production: PostgreSQL recommended)
- **ORM**: SQLAlchemy with Flask-SQLAlchemy
- **Authentication**: Flask-Login
- **PDF Generation**: ReportLab
- **XML Parsing**: lxml
- **Barcode**: Interleaved 2 of 5 (Febraban standard)
- **Frontend**: Bootstrap 5, Jinja2 templates

---

## 📦 Installation

### Prerequisites

- Python 3.12 or higher
- pip (Python package manager)
- Git

### Option 1: Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Luan-UNIC/julius.git
   cd julius
   ```

2. **Create virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database:**
   ```bash
   python -c "from app import init_db; init_db()"
   ```
   
   This creates:
   - Default users (cedente/cedente, agente/agente)
   - Bank configurations for Santander and BMP
   - Database schema

5. **Run application:**
   ```bash
   python app.py
   ```
   
   Application will be available at: `http://localhost:5000`

### Option 2: Docker Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Luan-UNIC/julius.git
   cd julius
   ```

2. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```
   
   Application will be available at: `http://localhost:5000`

3. **Stop containers:**
   ```bash
   docker-compose down
   ```

---

## 🚀 Usage

### Default Credentials

| Role    | Username | Password |
|---------|----------|----------|
| Cedente | cedente  | cedente  |
| Agente  | agente   | agente   |

**⚠️ Important**: Change default passwords in production!

### Cedente Workflow

#### 1. Configure Bank Settings

Navigate to **Settings** and configure for each bank:

**Santander Configuration:**
```
Agency:              3421
Account:             13000456-7
Wallet (Carteira):   101
Convenio:            3421130
Min Nosso Número:    1000000
Max Nosso Número:    9999999
Current Nosso Número: 1000000
```

**BMP Configuration:**
```
Agency:              0001
Account:             22345-1
Wallet (Carteira):   109
Convenio:            102030
Min Nosso Número:    2000000
Max Nosso Número:    8999999
Current Nosso Número: 2000000
```

#### 2. Upload Invoices

**Option A: XML Upload**
1. Click **Upload Invoice**
2. Select NFe or CTe XML file
3. System automatically extracts:
   - Payer name and document (CPF/CNPJ)
   - Invoice amount
   - Issue date
   - Document number

**Option B: Manual Entry**
1. Click **Manual Entry**
2. Fill form with:
   - Payer name
   - Payer CPF/CNPJ
   - Amount
   - Issue date
   - Document number
3. Optionally attach supporting document (PDF)

#### 3. Generate Boletos

1. Go to **Dashboard**
2. Select invoices to include in boleto
3. Choose target bank (Santander or BMP)
4. Click **Generate Boleto**

System will:
- Group invoices by payer CPF/CNPJ
- Atomically assign nosso_numero
- Calculate Febraban-compliant barcode
- Generate digitable line
- Create PDF boleto
- Update invoice statuses

#### 4. Download Boletos

- Click **Download PDF** next to each boleto
- Print or email to payer
- Boleto includes barcode, digitable line, payment instructions

### Agente Workflow

#### 1. Review Boletos

1. Login as **agente**
2. View all generated boletos in dashboard
3. Click **View Lastros** to see linked invoices
4. Verify amounts, payers, due dates

#### 2. Approve Boletos

1. Select boletos to approve
2. Click **Aprovar Selecionados**
3. Boleto status changes: `printed` → `selected`

#### 3. Generate CNAB Remittance

1. Click **Gerar Arquivo Remessa**
2. System generates CNAB file:
   - Santander: CNAB 240 format
   - BMP: CNAB 400 format
   - Filename: `CB{DDMM}{SEQ}.REM`
3. Boleto statuses update: `selected` → `registered`
4. Download CNAB file

#### 4. Submit to Bank

1. Access bank portal (Internet Banking PJ)
2. Navigate to Cobrança → Remessa
3. Upload generated `.REM` file
4. Bank processes and confirms registration

---

## ⚙️ Configuration

### Database Configuration

**Default (SQLite):**
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fidc.db'
```

**PostgreSQL (Production):**
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/fidc'
```

### Security Configuration

**Update secret key:**
```python
# In app.py
app.config['SECRET_KEY'] = 'your-strong-secret-key-here'
```

Generate secure key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### File Upload Configuration

```python
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size
```

---

## 📚 Documentation

### Comprehensive Documentation

- **[CHANGES.md](CHANGES.md)**: Complete implementation documentation including:
  - Architectural decisions and rationale
  - Technical implementation details
  - CNAB format specifications
  - Usage guide
  - Testing recommendations
  - Future enhancements

### Code Documentation

All modules include comprehensive docstrings:

- **services.py**: Business logic, CNAB generation, PDF creation
- **models.py**: Database schema and relationships
- **app.py**: Routes, authentication, request handling
- **utils.py**: Helper functions (DV calculation)

### CNAB Specifications

- **Santander CNAB 240**: `Layout-Cobranca-240-posicoes-padrao-Santander-Multibanco-jul-2025-Portugues.pdf`
- **BMP CNAB 400**: `Layout_CNAB_400-10 (6).pdf`

---

## 🔍 API Reference

### Route Overview

| Route | Method | Role | Description |
|-------|--------|------|-------------|
| `/` | GET | Any | Redirect to appropriate dashboard |
| `/login` | GET, POST | Public | User authentication |
| `/logout` | GET | Authenticated | User logout |
| `/cedente/dashboard` | GET | Cedente | View invoices and boletos |
| `/cedente/settings` | GET, POST | Cedente | Configure bank settings |
| `/upload` | GET | Cedente | Upload invoice page |
| `/upload/file` | POST | Cedente | Process XML upload |
| `/upload/manual` | POST | Cedente | Process manual entry |
| `/cedente/generate_boleto` | POST | Cedente | Generate boletos from invoices |
| `/download_boleto/<id>` | GET | Cedente | Download boleto PDF |
| `/view_lastro/<id>` | GET | Both | View invoice document |
| `/agente/dashboard` | GET | Agente | View all boletos |
| `/agente/approve` | POST | Agente | Approve selected boletos |
| `/agente/generate_remessa` | GET | Agente | Generate CNAB file |

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Initialization Fails

**Problem:** `OperationalError: no such table`

**Solution:**
```bash
# Delete existing database
rm fidc.db

# Reinitialize
python -c "from app import init_db; init_db()"
```

#### 2. Nosso Número Limit Reached

**Problem:** `"Nosso Numero limit reached for SANTANDER"`

**Solution:**
1. Login as cedente
2. Go to Settings
3. Increase **Max Nosso Número** value
4. Or reset **Current Nosso Número** if testing

#### 3. PDF Generation Error

**Problem:** Barcode not displaying in PDF

**Solution:**
- Ensure ReportLab is properly installed: `pip install --upgrade reportlab`
- Check barcode has exactly 44 digits
- Verify `createBarcodeDrawing` supports `I2of5`

#### 4. CNAB File Rejected by Bank

**Problem:** Bank returns validation errors

**Solution:**
1. Use bank's test tool (Santander: "Teste de Arquivos")
2. Verify agency, account, and convenio are correct
3. Check file encoding is ISO-8859-1
4. Verify line endings are CRLF (Windows format)
5. Ensure nosso_numero is within contracted range

#### 5. XML Parsing Fails

**Problem:** `"Failed to parse XML file"`

**Solution:**
- Verify XML is valid NFe or CTe format
- Check namespace is correct
- Try opening in XML editor to validate structure
- Ensure file is not corrupted

---

## 🧪 Testing

### Manual Testing

1. **Test Boleto Generation:**
   ```bash
   # Login as cedente
   # Upload sample_nfe.xml
   # Generate boleto for Santander
   # Verify PDF contains barcode and digitable line
   ```

2. **Test Atomic Nosso Número:**
   ```bash
   # Open two browser windows
   # Login as cedente in both
   # Simultaneously generate boletos
   # Verify no duplicate nosso_numero
   ```

3. **Test CNAB File:**
   ```bash
   # Generate boletos
   # Login as agente
   # Approve boletos
   # Generate remittance
   # Verify file has 240 (CNAB 240) or 400 (CNAB 400) chars per line
   ```

### Bank Validation

**Santander:**
1. Access Internet Banking PJ
2. Cobrança e Recebimentos → Teste de Arquivos
3. Upload generated `.REM` file
4. Review validation results

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 👥 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Review [CHANGES.md](CHANGES.md) for detailed documentation
- Check [Troubleshooting](#troubleshooting) section

---

## 🙏 Acknowledgments

- **Febraban**: For boleto barcode standards
- **Santander**: For CNAB 240 specification
- **BMP Money Plus**: For CNAB 400 specification
- **Flask Community**: For excellent web framework
- **ReportLab Team**: For PDF generation library

---

**Version:** 1.0.0  
**Last Updated:** December 8, 2025  
**Maintainer:** FIDC Development Team
