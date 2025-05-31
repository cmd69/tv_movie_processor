FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src

# Create media directory
# RUN mkdir -p /mnt/nfs/media && chmod 777 /mnt/nfs/media

# Expose port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "src/main.py"]
