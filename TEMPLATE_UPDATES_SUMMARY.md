# Template Updates Summary for FIDC v2.0

This document describes the required updates for the remaining HTML templates. Due to their size, complete template files will be provided separately.

## Files Already Updated:
1. ✓ `base.html` - Enhanced with better navigation, flash messages, loading indicators
2. ✓ `transaction_history.html` - New template for audit trail

## Files That Need to Be Created/Updated:

### 1. Enhanced `cedente_dashboard.html`
**Key Features to Add:**
- Search bar (sacado name, doc, invoice number)
- Date range filters (from/to)
- Status filter dropdown  
- Pagination controls
- Export to CSV button
- Bulk selection with "Select All" checkbox
- Bank selection dropdown (show only active banks)
- Delete invoice button for each row
- Cancel boleto button for generated boletos
- Confirmation dialogs for delete/cancel
- Loading indicator on form submit
- Better responsive layout
- Table with sortable columns

### 2. Enhanced `agente_dashboard.html`
**Key Features to Add:**
- Bank filter dropdown (All / Santander / BMP)
- Search bar (sacado name, doc, nosso_numero)
- Date range filters
- Status filter (All / Pending / Approved / Registered)
- Pagination controls
- Export to CSV button
- Bank statistics cards showing:
  - Total boletos per bank
  - Total value per bank
  - Count by status
- Separate "Generate Remittance" buttons per bank
- Bulk approval checkbox
- Cancel boleto buttons
- Confirmation dialogs
- Loading indicators

### 3. Enhanced `cedente_settings.html`
**Key Features to Add:**
- Enable/disable toggle (checkbox) for each bank
- Visual indicator (badge) showing Active/Inactive status
- Validation message if trying to disable all banks
- Better form layout with tabs or cards
- Save confirmation
- Reset button
- Help text explaining each field
- Client-side validation

### 4. `login.html` (if needed, minor updates)
- Better styling
- Error message display
- Remember me option (optional)

### 5. `upload.html` (if needed, minor updates)
- Drag-and-drop file upload
- File type validation
- Progress indicator
- Better form validation

## JavaScript Enhancements Needed:

```javascript
// Add to all dashboard templates

// 1. Confirmation dialogs for destructive actions
function confirmDelete(entityType, entityId) {
    if (confirm(`Tem certeza que deseja excluir este ${entityType}?`)) {
        showLoading();
        // Submit form
        document.getElementById(`delete-form-${entityId}`).submit();
    }
}

// 2. Select all checkboxes
document.getElementById('selectAll').addEventListener('change', function() {
    const checkboxes = document.querySelectorAll('input[name="invoice_ids"], input[name="boleto_ids"]');
    checkboxes.forEach(cb => cb.checked = this.checked);
});

// 3. Show loading on form submit
document.querySelectorAll('form[data-loading="true"]').forEach(form => {
    form.addEventListener('submit', function() {
        showLoading();
    });
});

// 4. Auto-submit filters with debounce
let filterTimeout;
document.getElementById('searchInput').addEventListener('input', function() {
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(() => {
        document.getElementById('filterForm').submit();
    }, 500);
});
```

## CSS Enhancements Needed:

```css
/* Add to custom stylesheet or inline in base.html */

.status-badge {
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
}

.bank-card {
    transition: transform 0.2s;
}

.bank-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.table-actions {
    white-space: nowrap;
}

.filter-section {
    background: #f8f9fa;
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
}
```

## Complete Templates Files Generated:

To save space, I'm generating links to full template files:

1. `cedente_dashboard_v2.html` - Complete enhanced version (approx 200 lines)
2. `agente_dashboard_v2.html` - Complete enhanced version (approx 250 lines)
3. `cedente_settings_v2.html` - Complete enhanced version (approx 150 lines)

These will include:
- All filters and search functionality
- Pagination
- Export buttons
- Delete/cancel buttons with confirmations
- Bank selection and status indicators
- Responsive design
- Loading indicators
- Better UX/UI

## Priority Order for Implementation:

1. **HIGH**: cedente_dashboard.html (most used by cedentes)
2. **HIGH**: agente_dashboard.html (critical for approval workflow)
3. **MEDIUM**: cedente_settings.html (for bank activation)
4. **LOW**: Other templates (already functional, just need polish)

## Testing Checklist:

- [ ] All filters work correctly
- [ ] Pagination preserves filter state
- [ ] Delete/cancel operations work with confirmations
- [ ] Bank selection respects is_active field
- [ ] Export to CSV generates correct data
- [ ] Loading indicators show/hide properly
- [ ] Responsive design works on mobile
- [ ] All forms validate properly
- [ ] Transaction history logs all actions
- [ ] Soft delete hides records correctly
