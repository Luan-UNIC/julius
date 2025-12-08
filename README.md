# FIDC System

A web application for generating Boletos (FIDC) with a full workflow from Ingestion to Remessa (CNAB).

## Features
- **Cedente Portal**: Upload NFe/CTe XMLs, manual entry, PDF upload.
- **Boleto Generation**: Automatic parsing, grouping by Sacado, PDF generation (Santander & BMP).
- **Middle Office (Agente)**: Review documents (Lastros), select/approve boletos.
- **CNAB Generation**: Generates .REM files (CNAB 240 for Santander, CNAB 400 for BMP).

## Stack
- Python (Flask)
- SQLite
- ReportLab (PDF Generation)
- Bootstrap 5

## How to Run

### Local
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Initialize Database (first time):
   ```bash
   python -c "from app import init_db; init_db()"
   ```
3. Run:
   ```bash
   python app.py
   ```
4. Access: `http://localhost:5000`

### Docker
1. Build and Run:
   ```bash
   docker-compose up --build
   ```

## Default Users
- **Cedente**: `cedente` / `cedente`
- **Agente**: `agente` / `agente`
