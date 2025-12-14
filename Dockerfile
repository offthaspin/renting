# Use Debian bookworm slim with Python 3.13
FROM python:3.13.4-slim-bookworm

# Install REQUIRED system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev build-essential \
    libffi-dev libssl-dev \
    libcairo2-dev pkg-config \
    python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
    libgirepository1.0-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of your app
COPY . .

# Expose default port for Render
EXPOSE 10000

# Start your app (adjust module if needed)
CMD ["gunicorn", "rentme.app:app", "-b", "0.0.0.0:10000", "--workers", "3"]
