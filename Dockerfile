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

# Copy only dependency files first
COPY pyproject.toml README.md ./

# Install build dependencies and build wheels for dependencies
RUN pip install --upgrade pip && \
    pip install wheel hatchling editables && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels hatchling editables openai pyyaml

# Now copy the source code
COPY src ./src/

# Build the package as a wheel
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels .

# Final stage
FROM python:3.10-alpine

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC \
    MAILMIND_LOGS_DIR=/home/mailmind/logs \
    MAILMIND_STATE_DIR=/home/mailmind/.mailmind

# Create non-root user and required directories
RUN addgroup -S mailmind && \
    adduser -S -G mailmind mailmind && \
    mkdir -p /config /home/mailmind/logs /home/mailmind/.mailmind && \
    chown -R mailmind:mailmind /config /home/mailmind

# Copy wheels from builder stage
COPY --from=builder /app/wheels /wheels

# Install dependencies first
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels \
    hatchling editables openai pyyaml

# Copy and install the app last
COPY src ./src/
RUN pip install --no-cache-dir --no-index --find-links=/wheels mailmind && \
    rm -rf /wheels

# Set volumes
VOLUME ["/config", "/home/mailmind"]

# Add metadata
LABEL version="1.0.0" \
    description="Email filtering and categorization tool"

# Add a healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD mailmind --version || exit 1

# Switch to non-root user
USER mailmind

# Set entrypoint and default command
ENTRYPOINT ["mailmind"]
CMD ["--config", "/config/config.yaml", "--daemon"] 