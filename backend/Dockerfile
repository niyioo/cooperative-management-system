# /backend/Dockerfile
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (needed for PostgreSQL)
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# ✅ 1. COPY THE PROJECT FILES FIRST
COPY . /app/

# ✅ 2. THEN RUN COLLECTSTATIC (It needs manage.py and your settings to exist)
# We inject a fake SQLite database URL so Django doesn't try to connect to Postgres during the build
RUN SECRET_KEY=dummy-key-for-build DATABASE_URL=sqlite:////tmp/dummy.db python manage.py collectstatic --noinput

CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"]