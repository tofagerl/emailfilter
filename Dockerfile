FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC

# Install dependencies
RUN pip install --upgrade pip

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src/

# Install the package
RUN pip install -e .

# Create directory for configuration
RUN mkdir -p /config

# Set volume for configuration
VOLUME /config

# Add a healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD emailfilter --version || exit 1

# Set entrypoint
ENTRYPOINT ["emailfilter"]

# Default command (can be overridden)
CMD ["daemon", "--config", "/config/config.yaml"] 