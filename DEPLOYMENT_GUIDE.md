# FIDC v2.0 Deployment & Testing Guide

## Pre-Deployment Checklist

### 1. Code Review
- [ ] All new models fields added
- [ ] All routes updated with proper authorization
- [ ] Transaction logging implemented
- [ ] Error handling improved
- [ ] Templates updated with new features

### 2. Database Migration
- [ ] Backup existing database (`cp fidc.db fidc.db.backup`)
- [ ] Run migration script (`python migrate_db.py`)
- [ ] Verify migration success
- [ ] Test rollback if needed

### 3. Dependencies
```bash
pip install -r requirements.txt
```

New dependencies in v2.0:
- `python-barcode` - Improved barcode generation
- `Pillow` - Image processing for barcodes

### 4. Configuration Validation
- [ ] Check SECRET_KEY is not default value (production)
- [ ] Verify UPLOAD_FOLDER exists and is writable
- [ ] Confirm database URI is correct
- [ ] Enable logging (file-based for production)

---

## Testing Plan

### Phase 1: Unit Testing (Core Functions)

#### Test Soft Delete
```python
# Test invoice soft delete
invoice = Invoice.query.first()
invoice.deleted_at = datetime.utcnow()
invoice.deleted_by = user.id
db.session.commit()

# Verify filtered out
active = Invoice.query.filter_by(deleted_at=None).all()
assert invoice not in active
```

#### Test Bank Activation
```python
# Disable bank
bank_config.is_active = False
db.session.commit()

# Try to generate boleto with disabled bank
is_valid, msg = validate_bank_selection('santander', user.id)
assert not is_valid
```

#### Test Transaction Logging
```python
# Generate boleto
boleto = create_boleto(...)
log_transaction('boleto', boleto.id, 'created', {...})

# Verify logged
history = TransactionHistory.query.filter_by(
    entity_type='boleto',
    entity_id=boleto.id
).first()
assert history is not None
```

---

### Phase 2: Integration Testing (Workflows)

#### Workflow 1: Complete Boleto Lifecycle
```
1. Login as cedente
2. Configure bank (enable Santander)
3. Upload NFe XML
4. Generate boleto
5. Verify PDF downloads
6. Verify transaction logged
7. Login as agente
8. Approve boleto
9. Generate CNAB for Santander
10. Verify file downloads
11. Check transaction history
```

#### Workflow 2: Bank Switching
```
1. Configure both banks
2. Generate boleto with Santander
3. Disable Santander
4. Try to generate boleto with Santander (should fail)
5. Generate boleto with BMP (should succeed)
6. Re-enable Santander
7. Verify both banks work
```

#### Workflow 3: Delete/Cancel Operations
```
1. Create invoice
2. Try to delete (should succeed)
3. Create invoice
4. Generate boleto from it
5. Try to delete invoice (should fail - linked to boleto)
6. Cancel boleto
7. Try to delete invoice (should succeed now)
8. Verify transaction history shows all actions
```

---

### Phase 3: Edge Cases & Error Handling

#### Test 1: Nosso Número Exhaustion
```
1. Set max_nosso_numero to current + 1
2. Generate one boleto (should succeed)
3. Try to generate another (should fail with clear message)
4. Increase max_nosso_numero
5. Generate another (should succeed)
```

#### Test 2: Concurrent Boleto Generation
```
# Simulate race condition
# Two users generating boletos simultaneously
# Verify no duplicate nosso_numero
# Database locking should prevent this
```

#### Test 3: Invalid File Uploads
```
1. Try uploading non-XML file as NFe
2. Try uploading corrupted XML
3. Verify error messages are user-friendly
4. Verify no database corruption
```

#### Test 4: Permission Violations
```
1. Login as cedente A
2. Try to delete invoice of cedente B (should fail)
3. Try to access agente routes (should fail)
4. Verify proper authorization checks
```

---

### Phase 4: UI/UX Testing

#### Visual Tests
- [ ] All pages render correctly on Chrome/Firefox/Safari
- [ ] Mobile responsive design works (320px to 1920px)
- [ ] Loading indicators appear during long operations
- [ ] Flash messages display and auto-dismiss
- [ ] Confirmation dialogs prevent accidental actions
- [ ] Forms validate before submission

#### Accessibility
- [ ] Tab navigation works
- [ ] Screen reader compatible (basic)
- [ ] Color contrast sufficient
- [ ] Buttons have proper labels

---

### Phase 5: Performance Testing

#### Load Testing
```python
# Test with large datasets
# 1000 invoices
# 5000 boletos
# 10000 transaction history records

# Verify pagination works
# Verify search is fast
# Verify export doesn't timeout
```

#### Database Performance
```sql
-- Check query performance
EXPLAIN QUERY PLAN SELECT * FROM boleto WHERE deleted_at IS NULL AND status='pending';

-- Verify indexes are used
PRAGMA index_list('boleto');
```

---

## Deployment Steps

### Development Environment

```bash
# 1. Clone/pull latest code
git pull origin main  # or extract zip

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migration (if upgrading from v1.0)
python migrate_db.py

# 5. Start application
python app.py

# 6. Access at http://localhost:5000
```

---

### Production Deployment (Linux Server)

```bash
# 1. Setup user and directory
sudo useradd -m -s /bin/bash fidc
sudo mkdir /opt/fidc
sudo chown fidc:fidc /opt/fidc

# 2. Copy application files
sudo cp -r /path/to/app/* /opt/fidc/
sudo chown -R fidc:fidc /opt/fidc

# 3. Install system dependencies
sudo apt-get update
sudo apt-get install python3.12 python3-pip python3-venv nginx supervisor

# 4. Setup virtual environment
cd /opt/fidc
sudo -u fidc python3 -m venv venv
sudo -u fidc venv/bin/pip install -r requirements.txt

# 5. Run migration
sudo -u fidc venv/bin/python migrate_db.py

# 6. Configure Gunicorn
sudo -u fidc venv/bin/pip install gunicorn

# Create gunicorn config: /opt/fidc/gunicorn_config.py
cat > /opt/fidc/gunicorn_config.py << EOF
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
timeout = 120
accesslog = "/var/log/fidc/access.log"
errorlog = "/var/log/fidc/error.log"
loglevel = "info"
EOF

# 7. Configure Supervisor
sudo tee /etc/supervisor/conf.d/fidc.conf << EOF
[program:fidc]
command=/opt/fidc/venv/bin/gunicorn -c /opt/fidc/gunicorn_config.py app:app
directory=/opt/fidc
user=fidc
autostart=true
autorestart=true
stderr_logfile=/var/log/fidc/stderr.log
stdout_logfile=/var/log/fidc/stdout.log
environment=PYTHONPATH="/opt/fidc",FLASK_ENV="production"
EOF

sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start fidc

# 8. Configure Nginx
sudo tee /etc/nginx/sites-available/fidc << EOF
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    location /static {
        alias /opt/fidc/static;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/fidc /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 9. Setup SSL with Let's Encrypt
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com

# 10. Setup log rotation
sudo tee /etc/logrotate.d/fidc << EOF
/var/log/fidc/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    sharedscripts
    postrotate
        supervisorctl restart fidc > /dev/null
    endscript
}
EOF
```

---

### Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Backup database
docker-compose exec web cp /app/fidc.db /app/backups/fidc_$(date +%Y%m%d).db
```

---

## Post-Deployment Verification

### Smoke Tests

```bash
# 1. Check application is running
curl -I http://your-domain.com

# 2. Test login page loads
curl http://your-domain.com/login

# 3. Check database is accessible
sqlite3 /opt/fidc/fidc.db "SELECT COUNT(*) FROM user;"

# 4. Verify logs are being written
tail -f /var/log/fidc/error.log

# 5. Test user login (manual)
# - Login as cedente
# - Login as agente
# - Verify dashboards load

# 6. Generate test boleto
# - Upload sample invoice
# - Generate boleto
# - Download PDF
# - Verify barcode renders

# 7. Test remittance generation
# - Approve test boleto
# - Generate CNAB file
# - Verify file downloads
# - Check file format (should be ISO-8859-1)
```

---

## Rollback Plan

If deployment fails:

```bash
# 1. Stop application
sudo supervisorctl stop fidc

# 2. Restore database backup
cp /opt/fidc/fidc.db.backup /opt/fidc/fidc.db

# 3. Restore previous code version
cd /opt/fidc
git checkout v1.0  # or restore from backup

# 4. Reinstall old dependencies
venv/bin/pip install -r requirements.txt

# 5. Restart application
sudo supervisorctl start fidc

# 6. Verify old version works
curl http://your-domain.com
```

---

## Monitoring

### Health Checks

```bash
# CPU and Memory
top -bn1 | grep python

# Disk space
df -h /opt/fidc

# Database size
du -h /opt/fidc/fidc.db

# Active connections
netstat -an | grep :8000 | wc -l

# Error rate
grep ERROR /var/log/fidc/error.log | wc -l
```

### Alerts

Setup monitoring for:
- [ ] Application downtime (>1 min)
- [ ] High error rate (>10 errors/min)
- [ ] Disk space low (<10% free)
- [ ] Database growing too fast (>100MB/day)
- [ ] Response time slow (>5 seconds)

---

## Security Checklist

- [ ] Change default passwords
- [ ] Use strong SECRET_KEY (32+ random characters)
- [ ] Enable HTTPS
- [ ] Configure firewall (allow only 80, 443, 22)
- [ ] Setup fail2ban for SSH
- [ ] Regular security updates (`apt-get upgrade`)
- [ ] Backup encryption
- [ ] Database encryption at rest (optional)
- [ ] Regular penetration testing
- [ ] Audit user access logs

---

## Backup Strategy

### Daily Backups

```bash
#!/bin/bash
# /opt/fidc/scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/fidc/backups"
DB_FILE="/opt/fidc/fidc.db"

# Create backup
mkdir -p $BACKUP_DIR
cp $DB_FILE "$BACKUP_DIR/fidc_$DATE.db"

# Compress
gzip "$BACKUP_DIR/fidc_$DATE.db"

# Delete backups older than 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

# Upload to S3 (optional)
# aws s3 cp "$BACKUP_DIR/fidc_$DATE.db.gz" s3://your-bucket/fidc-backups/
```

Add to crontab:
```bash
0 2 * * * /opt/fidc/scripts/backup.sh
```

---

## Support & Maintenance

### Regular Maintenance Tasks

**Weekly**:
- Review error logs
- Check disk space
- Verify backups are working
- Test restore procedure

**Monthly**:
- Update dependencies (`pip install --upgrade -r requirements.txt`)
- Review transaction history size
- Optimize database (`VACUUM;`)
- Security updates

**Quarterly**:
- Full disaster recovery drill
- Performance testing
- User access review
- Update documentation

---

## Troubleshooting Common Issues

### Application Won't Start

```bash
# Check logs
tail -100 /var/log/fidc/error.log

# Check supervisor status
sudo supervisorctl status fidc

# Test manually
cd /opt/fidc
venv/bin/python app.py
```

### Database Locked

```bash
# Check for zombie processes
ps aux | grep python

# Kill if needed
sudo kill -9 <PID>

# Restart application
sudo supervisorctl restart fidc
```

### High Memory Usage

```bash
# Check which process
ps aux --sort=-%mem | head

# Increase workers if needed (gunicorn_config.py)
# Or reduce workers if memory limited
```

---

## Support Contacts

- **Technical Issues**: [System Admin Email]
- **Database Issues**: [DBA Contact]
- **Infrastructure**: [DevOps Contact]
- **Security**: [Security Team]

---

**Version**: 2.0.0  
**Last Updated**: December 2024  
**Owner**: FIDC Development Team
