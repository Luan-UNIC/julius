# FIDC Middleware - Version 2.0.0 Change Log

## Major Enhancements and New Features

### 1. Soft Delete with Transaction History 🔍

**Motivation**: Maintain data integrity and provide complete audit trail for compliance.

**Implementation**:
- Added `deleted_at` and `deleted_by` fields to `Boleto` and `Invoice` models
- Soft delete preserves historical data while hiding records from normal queries
- All queries updated to filter `deleted_at IS NULL` by default
- Created new `TransactionHistory` model to track all operations

**New Models**:
```python
class TransactionHistory(db.Model):
    - timestamp: When action occurred
    - user_id: Who performed the action
    - entity_type: 'boleto' or 'invoice'
    - entity_id: ID of affected entity
    - action: 'created', 'updated', 'deleted', 'approved', 'cancelled', 'registered'
    - details: JSON with additional context
    - ip_address: User's IP for security audit
```

**New Routes**:
- `POST /cedente/delete_invoice/<id>` - Soft delete invoice (cedente only)
- `POST /cedente/cancel_boleto/<id>` - Cancel boleto (cedente only)
- `POST /agente/cancel_boleto/<id>` - Cancel boleto (agent with more permissions)
- `GET /history` - View transaction history with filters

**Business Rules**:
- Cedentes can only delete their own invoices/boletos
- Cannot delete invoice linked to a boleto (must cancel boleto first)
- Cannot cancel boletos with status 'registered'
- Agents can cancel any non-registered boleto
- All operations are logged to transaction_history

---

### 2. Bank Activation Control 🏦

**Motivation**: Allow cedentes to selectively use specific banks without deleting configurations.

**Implementation**:
- Added `is_active` boolean field to `BankConfig` model
- Cedente settings page now has enable/disable toggle for each bank
- Validation ensures at least one bank remains active
- Bank selection in boleto generation respects `is_active` status

**Updated Routes**:
- `POST /cedente/settings` - Now handles `is_active` field per bank
- `POST /cedente/generate_boleto` - Validates selected bank is active

**UI Changes**:
- Settings page shows Active/Inactive badges
- Toggle switches for each bank
- Client-side validation prevents disabling all banks
- Only active banks appear in boleto generation dropdown

---

### 3. Bank-Specific Remittance Generation 📄

**Motivation**: Banks require separate CNAB files; mixed files cause processing errors.

**Implementation**:
- Deprecated `/agente/generate_remessa` (old route)
- New route: `/agente/generate_remessa/<bank_code>` generates bank-specific files
- Agent dashboard groups boletos by bank with statistics
- Separate "Generate Remittance" button per bank

**Key Changes**:
- Boletos grouped by bank code ('033' Santander, '274' BMP)
- Filename includes bank identifier and date
- Transaction history logs which bank file was generated
- Dashboard shows per-bank statistics (count, total value, status breakdown)

**Example Workflow**:
1. Agent filters boletos by bank (e.g., Santander)
2. Approves selected boletos
3. Clicks "Generate Remittance for Santander"
4. Receives `CB{DDMM}{SEQ}.REM` file for Santander only
5. Repeats for BMP if needed

---

### 4. Enhanced Barcode Rendering 📊

**Motivation**: Original barcodes had readability issues; some scanners couldn't read them.

**Implementation**:
- Increased bar width from 0.33mm to 0.43mm for better readability
- Added proper quiet zones (10x bar width on each side)
- Implemented fallback to `python-barcode` library if ReportLab fails
- Third fallback displays barcode digits as text

**Technical Details**:
```python
# Primary: ReportLab Interleaved 2 of 5
bc = createBarcodeDrawing(
    'I2of5',
    value=clean_barcode,
    barWidth=0.43 * mm,  # Improved
    barHeight=13 * mm,
    checksum=0,
    bearers=0,
    quiet=1,
    lquiet=10,  # Left quiet zone
    rquiet=10   # Right quiet zone
)

# Fallback: python-barcode library
ITF = barcode.get_barcode_class('itf')
itf = ITF(clean_barcode, writer=ImageWriter())
```

---

### 5. Boleto Status Workflow Update 🔄

**Old Status Values**:
- `printed` → Created boleto (confusing name)
- `selected` → Approved by agent
- `registered` → Sent to bank

**New Status Values**:
- `pending` → Created, awaiting approval
- `approved` → Approved by agent, ready for remittance
- `cancelled` → Cancelled (soft deleted)
- `registered` → Included in CNAB file

**Migration**: `migrate_db.py` automatically updates old status values.

---

### 6. Search, Filters, and Pagination 🔍

**Cedente Dashboard**:
- Search by: sacado name, CPF/CNPJ, document number
- Filters: status, date range
- Pagination: 20/50/100 items per page
- Export to CSV

**Agent Dashboard**:
- Search by: sacado name, CPF/CNPJ, nosso_numero
- Filters: bank, status, date range
- Pagination: 20/50/100 items per page
- Bank statistics cards
- Export to CSV

**Implementation**:
```python
# Example query with filters
query = get_active_invoices()
if search:
    query = query.filter(
        db.or_(
            Invoice.sacado_name.ilike(f'%{search}%'),
            Invoice.sacado_doc.ilike(f'%{search}%')
        )
    )
if date_from:
    query = query.filter(Invoice.issue_date >= date_from)
pagination = query.paginate(page=page, per_page=per_page)
```

---

### 7. CSV Export Functionality 📥

**New Routes**:
- `GET /export/invoices` - Export cedente's invoices to CSV
- `GET /export/boletos` - Export boletos to CSV (role-aware)

**Features**:
- UTF-8 encoding
- Brazilian date format (DD/MM/YYYY)
- Filename includes timestamp
- Respects soft delete (only exports non-deleted records)
- Agents see all boletos, cedentes see only their own

**Example Output**:
```csv
ID,Tipo,Sacado,CPF/CNPJ,Valor,Data Emissão,Nº Documento,Status,Criado em
1,nfe,ACME Corp,12.345.678/0001-90,1500.00,10/12/2024,12345,pending,08/12/2024 10:30
```

---

### 8. Improved Error Handling and User Messages 💬

**Changes**:
- User-friendly Portuguese messages throughout
- Categorized flash messages: success, error, warning, info
- Icons for each message type
- Auto-dismiss after 5 seconds
- Detailed logging for debugging

**Before**:
```python
flash('Invalid credentials')
```

**After**:
```python
flash('Usuário ou senha inválidos. Tente novamente.', 'error')
logger.warning(f"Failed login attempt for user: {username}")
```

---

### 9. Enhanced UI/UX 🎨

**Improvements**:
- Bootstrap Icons throughout
- Loading overlays for long operations
- Confirmation dialogs for destructive actions
- Responsive mobile design
- Improved navigation with dropdown menus
- Status badges with colors (pending=warning, approved=success, etc.)
- Better form validation

**JavaScript Utilities**:
```javascript
function showLoading() { /* Shows spinner */ }
function hideLoading() { /* Hides spinner */ }
function confirmAction(msg) { /* Confirmation dialog */ }
```

---

### 10. Security and Authorization Enhancements 🔒

**New Decorator**:
```python
@require_role('cedente')
def some_cedente_only_route():
    pass
```

**Authorization Rules**:
- Cedentes can only modify their own data
- Agents can view/approve all boletos
- Transaction history shows who did what and when
- IP addresses logged for security audit
- Soft delete prevents accidental permanent data loss

---

## Database Schema Changes

### New Fields:
- `bank_config.is_active` (Boolean, default=True)
- `invoice.deleted_at` (DateTime, nullable)
- `invoice.deleted_by` (Integer, FK to User)
- `boleto.deleted_at` (DateTime, nullable)
- `boleto.deleted_by` (Integer, FK to User)

### New Table:
- `transaction_history` (complete audit log)

### Updated Values:
- `boleto.status`: 'printed'→'pending', 'selected'→'approved'

---

## Migration Guide

### For Existing Installations:

1. **Backup your database**:
   ```bash
   cp fidc.db fidc.db.backup
   ```

2. **Run migration script**:
   ```bash
   python migrate_db.py
   ```

3. **Install new dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Restart application**:
   ```bash
   python app.py
   ```

### For New Installations:
Just run `python app.py` - all tables will be created automatically.

---

## API Changes

### Deprecated:
- `/agente/generate_remessa` - Use bank-specific route instead

### New Routes:
- `/agente/generate_remessa/<bank_code>` - Bank-specific remittance
- `/cedente/delete_invoice/<id>` - Soft delete invoice
- `/cedente/cancel_boleto/<id>` - Cancel boleto (cedente)
- `/agente/cancel_boleto/<id>` - Cancel boleto (agent)
- `/history` - Transaction history view
- `/export/invoices` - Export invoices CSV
- `/export/boletos` - Export boletos CSV

---

## Configuration Changes

No configuration file changes required. All settings managed through:
- Database (dynamic configuration)
- Environment variables (optional, for advanced users)

---

## Performance Improvements

1. **Indexed Soft Delete Fields**: Queries filtering `deleted_at` are fast
2. **Paginated Results**: Large datasets don't slow down UI
3. **Lazy Loading**: Related entities loaded only when needed
4. **Database Locking**: Atomic nosso_numero increment prevents race conditions

---

## Testing Recommendations

### Unit Tests:
- Soft delete filtering
- Bank activation validation
- Transaction history logging
- CSV export formatting

### Integration Tests:
- Full boleto workflow (create → approve → generate CNAB)
- Bank-specific remittance generation
- Delete/cancel with authorization
- Multi-user scenarios

### Manual Tests:
1. Create invoice → Generate boleto → Approve → Generate remittance
2. Test with both banks (Santander and BMP)
3. Disable one bank, verify it doesn't appear in boleto generation
4. Delete invoice, verify it's hidden but in transaction history
5. Cancel boleto, verify linked invoices return to pending
6. Export CSV, verify data format
7. Test barcode with scanner app

---

## Known Limitations

1. **Multi-Cedente CNAB**: Currently generates file for first cedente only if multiple detected
2. **Barcode Fallback**: Third fallback (text) is not scannable
3. **CSV Encoding**: Some Excel versions may require manual UTF-8 import
4. **Transaction History**: No automatic cleanup (grows indefinitely)

---

## Future Enhancements (Not in v2.0)

- Email notifications on boleto approval
- Automatic CNAB sequence number management
- Return file (retorno) processing
- Multi-factor authentication
- API REST endpoints
- Mobile app
- Advanced reporting dashboards
- Automated testing suite

---

## Credits

**Development Team**: FIDC Development Team
**Version**: 2.0.0
**Release Date**: December 2024
**License**: Proprietary

For support, contact your system administrator.
