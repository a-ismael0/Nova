FROM python:3.10-slim

# Install system dependencies including Chromium, ChromeDriver, Xvfb, and build tools
RUN apt-get update && apt-get install -y \
    chromium-driver \
    chromium \
    xvfb \
    unzip \
    gcc \
    python3-dev \
    libffi-dev \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose the port your Flask app runs on
EXPOSE 5000

# Run your Flask app
CMD ["python", "app.py"]
