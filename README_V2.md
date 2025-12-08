# FIDC Middleware System v2.0

> **Enterprise-Grade Brazilian Payment Slip (Boleto) Management System**
> 
> Multi-bank CNAB generation with audit trail, soft delete, and bank activation control

---

## 🚀 What's New in v2.0

- ✅ **Soft Delete & Transaction History** - Complete audit trail with undo capability
- ✅ **Bank Activation Control** - Enable/disable banks without losing configuration
- ✅ **Bank-Specific Remittance Files** - Separate CNAB files per bank
- ✅ **Enhanced Barcode Rendering** - Improved readability with multiple fallbacks
- ✅ **Search, Filters & Pagination** - Find anything quickly in large datasets
- ✅ **CSV Export** - Export data for reporting and analysis
- ✅ **Better UX/UI** - Loading indicators, confirmations, responsive design
- ✅ **Portuguese Localization** - User-friendly messages in Brazilian Portuguese

See [CHANGES_V2.md](CHANGES_V2.md) for complete details.

---

## 📋 Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Roles & Workflows](#user-roles--workflows)
- [Bank Configuration](#bank-configuration)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)
- [Migration from v1.0](#migration-from-v10)
- [FAQ](#faq)

---

## ✨ Features

### Core Functionality
- **Multi-Bank Support**: Santander (CNAB 240) and BMP Money Plus (CNAB 400)
- **Invoice Processing**: Upload NFe/CTe XML or manual entry
- **Boleto Generation**: Febraban-compliant with barcode and digitable line
- **CNAB File Generation**: Bank-ready remittance files with proper encoding
- **Atomic Operations**: Database locking prevents nosso_numero conflicts

### New in v2.0
- **Soft Delete**: Never lose data, with full recovery capability
- **Transaction History**: Complete audit trail of all operations
- **Bank Activation**: Enable/disable banks dynamically
- **Advanced Search**: Filter by sacado, date, status, bank
- **Pagination**: Handle thousands of records efficiently
- **CSV Export**: Download data for external analysis
- **Enhanced Security**: IP logging, role-based access, authorization checks

### User Experience
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Loading Indicators**: Visual feedback for long operations
- **Confirmation Dialogs**: Prevent accidental deletions
- **Smart Validation**: Client and server-side validation
- **Helpful Messages**: Clear error messages in Portuguese

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Web Browser (Client)                 │
│  - Bootstrap 5 UI                                        │
│  - JavaScript (loading, confirmations, validation)       │
└────────────────┬────────────────────────────────────────┘
                 │ HTTP/HTTPS
┌────────────────┴────────────────────────────────────────┐
│                  Flask Application Server                 │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │   app.py    │  │  services.py │  │   models.py     │ │
│  │  (Routes)   │  │  (Business)  │  │  (Data Layer)   │ │
│  └─────────────┘  └──────────────┘  └─────────────────┘ │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │           Flask-Login (Authentication)               │ │
│  └─────────────────────────────────────────────────────┘ │
└────────────────┬────────────────────────────────────────┘
                 │ SQL
┌────────────────┴────────────────────────────────────────┐
│                    SQLite Database                        │
│  - Users, BankConfig, Invoices, Boletos                  │
│  - TransactionHistory (audit trail)                      │
│  - Soft delete support                                   │
└───────────────────────────────────────────────────────────┘
```

**Technology Stack**:
- **Backend**: Python 3.12, Flask 3.x, SQLAlchemy, Flask-Login
- **Frontend**: Bootstrap 5, Bootstrap Icons, vanilla JavaScript
- **Database**: SQLite (easily upgradable to PostgreSQL/MySQL)
- **PDF Generation**: ReportLab
- **Barcode**: ReportLab + python-barcode (fallback)
- **XML Parsing**: lxml

---

## 🔧 Installation

### Prerequisites
- Python 3.10+ (3.12 recommended)
- pip (Python package manager)
- Git (optional, for cloning)

### Local Installation

```bash
# 1. Clone or extract project
cd /path/to/project

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize database (first run only)
python app.py
# Database will be created automatically with default users

# 4. Access application
# Open browser to: http://localhost:5000
```

### Docker Installation

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# Access application
# Open browser to: http://localhost:5000
```

### Migration from v1.0

```bash
# 1. Backup your database
cp fidc.db fidc.db.backup

# 2. Install new dependencies
pip install -r requirements.txt

# 3. Run migration script
python migrate_db.py

# 4. Restart application
python app.py
```

---

## 🚀 Quick Start

### Default Credentials

**Cedente (Invoice Creator)**:
- Username: `cedente`
- Password: `cedente`

**Agente (Approver)**:
- Username: `agente`
- Password: `agente`

⚠️ **Change these passwords in production!**

### Basic Workflow

#### 1. Configure Banks (Cedente)
```
Login as cedente → Settings → Configure Santander & BMP → Save
```

#### 2. Upload Invoice (Cedente)
```
Dashboard → Upload New Invoice → Choose NFe/CTe XML → Submit
```

#### 3. Generate Boleto (Cedente)
```
Dashboard → Select invoices → Choose bank → Generate Boletos
```

#### 4. Approve Boletos (Agente)
```
Login as agente → Dashboard → Select boletos → Approve
```

#### 5. Generate CNAB (Agente)
```
Dashboard → Filter by bank → Generate Remittance for [Bank]
```

#### 6. Submit to Bank
```
Upload .REM file to bank's portal
```

---

## 👥 User Roles & Workflows

### Cedente Role (Beneficiary)

**Capabilities**:
- Configure bank accounts (Santander and/or BMP)
- Enable/disable banks
- Upload fiscal documents (NFe, CTe, or manual)
- Generate boletos from invoices
- Download boleto PDFs
- View own invoices and boletos
- Delete own invoices (soft delete)
- Cancel own boletos (if not registered)
- Export data to CSV
- View transaction history (own actions only)

**Typical Workflow**:
1. Configure bank settings (one-time)
2. Upload invoices (daily/weekly)
3. Generate boletos (batch or individual)
4. Download PDF boletos
5. Monitor status in dashboard

---

### Agente Role (Financial Agent)

**Capabilities**:
- View all boletos from all cedentes
- Filter by bank, status, date, sacado
- Approve boletos for remittance
- Generate bank-specific CNAB files
- Cancel boletos (wider permissions than cedente)
- Export data to CSV
- View complete transaction history (all users)
- Monitor bank statistics

**Typical Workflow**:
1. Review new boletos (status: pending)
2. Verify backing documents
3. Approve boletos
4. Filter by bank (Santander or BMP)
5. Generate remittance file for each bank
6. Submit files to respective banks
7. Monitor registrations

---

## 🏦 Bank Configuration

### Santander (FIDC Account)

**CNAB Format**: 240 (hierarchical)

**Required Fields**:
- **Agency**: 4 digits (e.g., `3421`)
- **Account**: 8 digits + check digit (e.g., `13000456-7`)
- **Wallet**: Usually `101` for cobrança rápida
- **Convênio**: Agreement code from Santander
- **Nosso Número Range**: 7-13 digits (e.g., 1000000 to 9999999)

**Example**:
```
Agency: 3421
Account: 13000456-7
Wallet: 101
Convênio: 3421130
Min NN: 1000000
Max NN: 9999999
Current NN: 1000000
Active: ✓ Yes
```

---

### BMP Money Plus (Escrow Account)

**CNAB Format**: 400 (flat)

**Required Fields**:
- **Agency**: 4 digits (e.g., `0001`)
- **Account**: 7 digits + check digit (e.g., `22345-1`)
- **Wallet**: Usually `109` for cobrança simples
- **Convênio**: Agreement code from BMP
- **Nosso Número Range**: 11 digits (e.g., 2000000 to 8999999)

**Example**:
```
Agency: 0001
Account: 22345-1
Wallet: 109
Convênio: 102030
Min NN: 2000000
Max NN: 8999999
Current NN: 2000000
Active: ✓ Yes
```

---

## 📚 API Documentation

### Cedente Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/cedente/dashboard` | View invoices with search/filter |
| GET | `/cedente/settings` | Bank configuration page |
| POST | `/cedente/settings` | Update bank settings |
| GET | `/upload` | Upload invoice page |
| POST | `/upload/file` | Upload NFe/CTe XML |
| POST | `/upload/manual` | Manual invoice entry |
| POST | `/cedente/generate_boleto` | Generate boletos from invoices |
| GET | `/download_boleto/<id>` | Download boleto PDF |
| POST | `/cedente/delete_invoice/<id>` | Soft delete invoice |
| POST | `/cedente/cancel_boleto/<id>` | Cancel boleto |
| GET | `/export/invoices` | Export invoices to CSV |
| GET | `/export/boletos` | Export boletos to CSV |
| GET | `/history` | View transaction history |

---

### Agente Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/agente/dashboard` | View all boletos with filters |
| POST | `/agente/approve` | Approve selected boletos |
| GET | `/agente/generate_remessa/<bank_code>` | Generate CNAB for specific bank |
| POST | `/agente/cancel_boleto/<id>` | Cancel any boleto |
| GET | `/export/boletos` | Export all boletos to CSV |
| GET | `/history` | View complete transaction history |

---

### Common Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Redirect to appropriate dashboard |
| GET/POST | `/login` | User authentication |
| GET | `/logout` | User logout |
| GET | `/view_lastro/<id>` | View invoice document |

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "Bank configuration not found"
**Solution**: Go to Settings and configure at least one bank account.

#### 2. "No invoices selected"
**Solution**: Check the checkboxes next to invoices before clicking Generate Boletos.

#### 3. "Invalid bank selection" or "Bank is disabled"
**Solution**: Go to Settings and enable the bank you want to use.

#### 4. "Nosso Numero limit reached"
**Solution**: Increase `max_nosso_numero` in bank settings, or contact your bank for new range.

#### 5. Barcode not readable
**Solution**: v2.0 has improved barcode rendering. Test with updated PDF. If still fails, check barcode digits manually.

#### 6. CNAB file rejected by bank
**Solution**: 
- Verify bank configuration (agency, account, wallet, convênio)
- Ensure CNAB format matches bank (Santander=240, BMP=400)
- Check file encoding (should be ISO-8859-1)
- Review bank's CNAB layout documentation

#### 7. Cannot delete invoice
**Solution**: Invoice linked to boleto cannot be deleted. Cancel the boleto first, then delete invoice.

#### 8. Transaction history not showing
**Solution**: History only shows actions after v2.0 upgrade. Previous actions not tracked.

---

### Logging

Application logs are written to console. For production, configure file logging:

```python
# Add to app.py
import logging
logging.basicConfig(
    filename='fidc.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## 💾 Database Schema

### Tables

1. **user** - System users (cedente/agente)
2. **bank_config** - Bank configurations with activation status
3. **invoice** - Uploaded/manual invoices with soft delete
4. **boleto** - Generated boletos with soft delete
5. **transaction_history** - Complete audit trail (NEW in v2.0)

### Key Relationships

```
User 1──N BankConfig
User 1──N Invoice
User 1──N Boleto
Invoice N──1 Boleto (boleto_id FK)
User 1──N TransactionHistory
```

### Indexes

All foreign keys and frequently queried fields are indexed for performance:
- `user_id`, `bank_type`, `is_active` on bank_config
- `user_id`, `status`, `deleted_at`, `boleto_id` on invoice
- `user_id`, `bank`, `status`, `deleted_at`, `due_date` on boleto
- `user_id`, `entity_type`, `action`, `timestamp` on transaction_history

---

## ❓ FAQ

**Q: Can I use both banks simultaneously?**  
A: Yes, you can configure and enable both banks. Choose which bank to use when generating each boleto.

**Q: What happens to nosso_numero when I cancel a boleto?**  
A: The nosso_numero is not reused. This prevents duplicates and maintains audit trail.

**Q: Can I recover deleted invoices?**  
A: Deleted records are soft-deleted (not permanently removed). Contact system administrator for recovery.

**Q: How do I change my password?**  
A: Currently requires database update. Run:
```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('newpass'))"
# Then update user table with generated hash
```

**Q: Can I have multiple cedentes?**  
A: Yes, create additional users with role='cedente'. Each has separate bank configurations and data.

**Q: Does it support other banks?**  
A: Not yet. v2.0 supports Santander and BMP. Additional banks require CNAB layout implementation.

**Q: Can I deploy to production?**  
A: Yes, but:
- Change default passwords
- Use PostgreSQL/MySQL instead of SQLite
- Enable HTTPS
- Configure proper backups
- Set up monitoring/logging
- Review security best practices

**Q: Is there an API?**  
A: Not in v2.0. All operations are web-based. REST API planned for future release.

**Q: How do I report bugs?**  
A: Contact your system administrator or development team.

---

## 📞 Support

For technical support, contact:
- **System Administrator**: [Your contact]
- **Development Team**: FIDC Development Team

For bank-specific questions, contact your bank relationship manager.

---

## 📄 License

**Proprietary Software**  
© 2024 FIDC Development Team. All rights reserved.

This software is licensed for use by authorized organizations only. Redistribution, modification, or reverse engineering is prohibited without written permission.

---

## 🎯 Roadmap

### Planned for v2.1
- [ ] Email notifications
- [ ] Return file (retorno) processing
- [ ] Advanced reporting dashboards
- [ ] User management UI (create/edit users)
- [ ] Password change UI

### Planned for v3.0
- [ ] REST API
- [ ] Additional banks support
- [ ] Multi-factor authentication
- [ ] Mobile app
- [ ] Real-time bank integration
- [ ] Automated testing suite

---

**Version**: 2.0.0  
**Last Updated**: December 2024  
**Documentation**: [CHANGES_V2.md](CHANGES_V2.md) | [TEMPLATE_UPDATES_SUMMARY.md](TEMPLATE_UPDATES_SUMMARY.md)
