FROM python:3.10-alpine AS builder

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src/

# Install build dependencies explicitly
RUN pip install --upgrade pip && \
    pip install wheel hatchling editables

# Build the package as a wheel
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels .

# Also build wheels for dependencies
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels hatchling editables openai pyyaml

# Final stage
FROM python:3.10-alpine

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Create non-root user and required directories
RUN addgroup -S emailfilter && \
    adduser -S -G emailfilter emailfilter && \
    mkdir -p /config /home/emailfilter/logs /home/emailfilter/.emailfilter && \
    chown -R emailfilter:emailfilter /config /home/emailfilter

# Copy wheels and project files from builder stage
COPY --from=builder /app/wheels /wheels
COPY src ./src/

# Install the package from wheels
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels emailfilter && \
    rm -rf /wheels

# Set volume for configuration
VOLUME /config
# Set volume for persistent data including SQLite database
VOLUME /home/emailfilter

# Add metadata
LABEL version="1.0.0" \
      description="Email filtering and categorization tool"

# Set environment variable for logs directory
ENV EMAILFILTER_LOGS_DIR=/home/emailfilter/logs
# Set environment variable for state directory
ENV EMAILFILTER_STATE_DIR=/home/emailfilter/.emailfilter

# Add a healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD emailfilter --version || exit 1

# Switch to non-root user
USER emailfilter

# Set entrypoint
ENTRYPOINT ["emailfilter"]

# Default command (can be overridden)
CMD ["imap", "--config", "/config/config.yaml", "--daemon"] 