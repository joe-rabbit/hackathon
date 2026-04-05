# Python service for Mochi Hackathon
FROM python:3.11-slim

# Set working directory
WORKDIR /hackathon

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY dashboard ./dashboard
COPY pI ./pI
COPY tamagochi ./tamagochi

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/hackathon

# Default command (can be overridden)
CMD ["bash"]
