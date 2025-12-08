# SQLAlchemy Relationship Ambiguity Fix

**Date**: December 8, 2025  
**Version**: 2.0.0  
**Issue**: AmbiguousForeignKeysError in Boleto and Invoice models

---

## Problem Description

The FIDC Middleware v2.0 was failing to initialize the database due to a SQLAlchemy relationship error:

```
AmbiguousForeignKeysError: Could not determine join condition between parent/child tables on relationship Boleto.user
```

### Root Cause

Both the `Boleto` and `Invoice` models had **two foreign keys** pointing to the `User` table:
1. `user_id` - The cedente who owns the record
2. `deleted_by` - The user who soft-deleted the record (v2.0 feature)

SQLAlchemy couldn't determine which foreign key to use for the relationship, causing an ambiguity error.

---

## Solution Applied

### Changes to `models.py`

#### 1. **Invoice Model** (Lines 130-132)

**Before:**
```python
# No explicit relationships defined
```

**After:**
```python
# Relationships - explicitly specify foreign_keys to avoid ambiguity
cedente = db.relationship('User', foreign_keys=[user_id], backref=db.backref('invoices', lazy=True))
deleted_by_user = db.relationship('User', foreign_keys=[deleted_by])
```

#### 2. **Boleto Model** (Lines 182-185)

**Before:**
```python
# Relationships
user = db.relationship('User', backref=db.backref('boletos', lazy=True))
invoices = db.relationship('Invoice', backref='boleto', lazy=True)
```

**After:**
```python
# Relationships - explicitly specify foreign_keys to avoid ambiguity
cedente = db.relationship('User', foreign_keys=[user_id], backref=db.backref('boletos', lazy=True))
deleted_by_user = db.relationship('User', foreign_keys=[deleted_by])
invoices = db.relationship('Invoice', backref='boleto', lazy=True)
```

---

## Key Changes

1. **Explicit `foreign_keys` parameter**: Added `foreign_keys=[user_id]` and `foreign_keys=[deleted_by]` to disambiguate which FK to use
2. **Relationship renaming**: 
   - `user` → `cedente` (more semantically accurate)
   - Added new `deleted_by_user` relationship for soft delete tracking
3. **No code changes required**: Existing code uses `user_id` directly, not the relationship

---

## Verification Tests

### Test 1: Database Initialization ✅
```bash
python3 -c "from app import app, init_db; init_db()"
```
**Result**: Database initialized without errors

### Test 2: Model Relationships ✅
```python
cedente = User.query.filter_by(role='cedente').first()
print(cedente.boletos)  # Works!
print(cedente.invoices)  # Works!

boleto = Boleto.query.first()
print(boleto.cedente)  # Works!
print(boleto.deleted_by_user)  # Works!
```
**Result**: All relationships accessible without errors

### Test 3: Application Startup ✅
```bash
python3 -c "from app import app"
```
**Result**: Flask application starts successfully

---

## Impact Assessment

### ✅ No Breaking Changes
- Existing code uses `user_id` directly (not the relationship)
- No changes needed in `app.py` or `services.py`
- Backward compatible with existing queries

### ✅ Benefits
- Resolves critical startup blocker
- More semantically correct naming (`cedente` vs `user`)
- Supports soft delete audit trail via `deleted_by_user`
- Follows SQLAlchemy best practices

---

## Related Models

### TransactionHistory Model
**Status**: No changes needed  
**Reason**: Only has one FK to User (`user_id`), no ambiguity

---

## Technical Notes

### SQLAlchemy Relationship Syntax
```python
relationship_name = db.relationship(
    'TargetModel',
    foreign_keys=[foreign_key_column],  # Explicitly specify FK
    backref='reverse_relationship_name'
)
```

### When to Use `foreign_keys` Parameter
Use when:
- A model has multiple FKs to the same table
- SQLAlchemy throws `AmbiguousForeignKeysError`
- You need explicit control over join conditions

---

## Conclusion

The SQLAlchemy relationship ambiguity has been **successfully resolved**. The FIDC Middleware v2.0 system can now:
- ✅ Initialize the database without errors
- ✅ Start the Flask application successfully  
- ✅ Support soft delete functionality with audit trails
- ✅ Maintain backward compatibility with existing code

**Status**: **RESOLVED** ✅
