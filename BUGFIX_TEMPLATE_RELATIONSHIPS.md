# Bug Fix: Template Relationship References

**Date:** December 8, 2025  
**Version:** v2.0.2  
**Issue:** Jinja2 template error due to outdated relationship references

## Problem Description

After fixing the SQLAlchemy relationship ambiguity in v2.0.1 (documented in `BUGFIX_SQLALCHEMY_RELATIONSHIPS.md`), the relationship name was changed from `user` to `cedente` in the `Boleto` and `Invoice` models for semantic accuracy. However, the Jinja2 templates still referenced the old `user` relationship, causing the following error:

```
jinja2.exceptions.UndefinedError: 'models.Boleto object' has no attribute 'user'
```

The error occurred in `agente_dashboard.html` at line 32 when trying to access `{{ boleto.user.username }}`.

## Root Cause

The relationship name change in models.py was not propagated to:
1. Jinja2 templates that accessed `boleto.user` or `invoice.user`
2. Python code in services.py that queried the user through `User.query.get(boleto.user_id)`

## Changes Made

### 1. Template Files

**File:** `templates/agente_dashboard.html`

**Line 32 - Before:**
```html
<td>{{ boleto.user.username }}</td>
```

**Line 32 - After:**
```html
<td>{{ boleto.cedente.username }}</td>
```

**Note:** `transaction_history.html` was checked but did NOT require changes because the `TransactionHistory` model still uses `user` as its relationship name (which is correct for that model's purpose of tracking which user performed an action).

### 2. Services File

**File:** `services.py`

**Lines 170-172 - Before:**
```python
for boleto in boletos:
    # Get bank config for this boleto's cedente
    boleto_cedente = User.query.get(boleto.user_id)
```

**Lines 170-172 - After:**
```python
for boleto in boletos:
    # Get bank config for this boleto's cedente
    boleto_cedente = boleto.cedente
```

**Lines 347-349 - Before:**
```python
for boleto in boletos:
    # Get bank config for this boleto
    boleto_cedente = User.query.get(boleto.user_id)
```

**Lines 347-349 - After:**
```python
for boleto in boletos:
    # Get bank config for this boleto
    boleto_cedente = boleto.cedente
```

**Benefit:** These changes eliminate unnecessary database queries by using the SQLAlchemy relationship directly instead of querying `User.query.get()`.

### 3. Files Checked (No Changes Required)

- **app.py**: All references use `boleto.user_id` or `invoice.user_id` (direct column access), which is correct and doesn't need to change.
- Other template files: No references to `boleto.user` or `invoice.user` found.

## Verification

### 1. Application Startup
✓ Flask application started successfully without errors

### 2. Relationship Access Test
Created and tested a Boleto object to verify the `cedente` relationship:
- ✓ `boleto.cedente` accessible
- ✓ `boleto.cedente.username` returns correct value
- ✓ `boleto.cedente.role` returns correct value
- ✓ Relationship matches direct `user_id` access

### 3. Template Rendering Test
Tested Jinja2 template rendering with `{{ boleto.cedente.username }}`:
- ✓ Template renders without errors
- ✓ Cedente username displays correctly in output
- ✓ No `UndefinedError` exceptions

### 4. Test Results
```
Found cedente user: cedente
✓ Boleto created successfully
✓ Cedente relationship works correctly!
✓ Template rendered successfully!
✓ Cedente username 'cedente' found in rendered output
🎉 All tests passed! The boleto.cedente relationship works correctly.
```

## Impact Analysis

### Breaking Changes
None. This fix corrects an existing bug introduced in v2.0.1.

### Performance Improvements
The changes to `services.py` actually **improve performance** by:
- Eliminating 2 unnecessary database queries per boleto in CNAB generation
- Using SQLAlchemy's relationship loading instead of explicit queries

### Backward Compatibility
- Direct column access (`boleto.user_id`, `invoice.user_id`) remains unchanged
- All existing code using `user_id` continues to work
- Only relationship access (`boleto.cedente`) has changed

## Files Modified

1. `templates/agente_dashboard.html` - Updated boleto.user → boleto.cedente
2. `services.py` - Updated User.query.get(boleto.user_id) → boleto.cedente (2 occurrences)

## Lessons Learned

When renaming SQLAlchemy relationships:
1. Search all templates for Jinja2 references to the old relationship name
2. Search Python code for both direct relationship access AND indirect queries
3. Test template rendering with real data
4. Consider using grep/ripgrep to find all occurrences: `grep -r "boleto\.user" .`

## Related Documentation

- `BUGFIX_SQLALCHEMY_RELATIONSHIPS.md` - Original relationship name change
- `models.py` - Model definitions with cedente relationships
- `CHANGES_V2.md` - Version 2.0 feature documentation
