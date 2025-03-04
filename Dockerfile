FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src/

# Install the package and its dependencies
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install -e . && \
    pip freeze > /app/requirements.txt && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels -r /app/requirements.txt

# Final stage
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Create non-root user
RUN groupadd -r emailfilter && \
    useradd -r -g emailfilter emailfilter && \
    mkdir -p /config /home/emailfilter && \
    chown -R emailfilter:emailfilter /config /home/emailfilter

# Copy wheels and project files from builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt /app/
COPY --from=builder /app/pyproject.toml /app/README.md ./
COPY src ./src/

# Install the package from wheels
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    pip install --no-cache-dir -e . && \
    rm -rf /wheels

# Set volume for configuration
VOLUME /config

# Add metadata
LABEL version="1.0.0" \
      description="Email filtering and categorization tool"

# Add a healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD emailfilter --version || exit 1

# Switch to non-root user
USER emailfilter

# Set entrypoint
ENTRYPOINT ["emailfilter"]

# Default command (can be overridden)
CMD ["daemon", "--config", "/config/config.yaml"] 