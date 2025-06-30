FROM python:3.10-slim

# Install Chrome + Xvfb + dependencies
RUN apt-get update && apt-get install -y \
    chromium-driver \
    chromium \
    xvfb \
    unzip \
    curl \
    wget \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99

# Set working directory
WORKDIR /app

# Copy code
COPY . .

# Install Python packages
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose port for Flask
EXPOSE 5000

# Run using Xvfb (for Selenium) and SocketIO
CMD ["xvfb-run", "python", "app.py"]
