FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    chromium-driver \
    chromium \
    xvfb \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set display variable for headless Chrome
ENV DISPLAY=:99

# Create working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose port
EXPOSE 5000

# Run the Flask app using eventlet for Socket.IO and Xvfb for headless browser
CMD ["xvfb-run", "python", "app.py"]
