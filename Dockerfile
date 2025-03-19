FROM python:3.13.2-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/

# Copy trained model
COPY models/email-classifier-v2/final /app/models/email-classifier

# Set Python path and model path
ENV PYTHONPATH=/app/src
ENV MODEL_PATH=/app/models/email-classifier

# Default command (can be overridden)
ENTRYPOINT ["python", "-m", "mailmind.inference.cli"]
CMD ["--help"] 