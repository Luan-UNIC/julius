FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required for lxml and reportlab
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize DB (if not exists)
# Note: In a real production setup with persistent volumes, 
# this might need to be done in an entrypoint script to ensure it runs on container startup
# if the volume is mounted over. For now, we rely on the check in app.py's __main__ or this step.
RUN python -c "from app import init_db; init_db()"

EXPOSE 5000

CMD ["python", "app.py"]
