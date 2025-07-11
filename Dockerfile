# Multi-stage Dockerfile for Nomos
# Stage 1: Builder stage for installing dependencies and building the package
FROM python:3.12-slim AS builder

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY nomos/ ./nomos/
COPY README.md ./

# Create virtual environment and install all dependencies including optional ones
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install build tools
RUN pip install --upgrade pip setuptools wheel

# Install the package with all optional dependencies
RUN pip install -e ".[cli,mcp,anthropic,openai,mistralai,google,ollama,huggingface,traces,serve,dev]"

# Stage 2: Runtime stage with minimal dependencies
FROM python:3.12-slim AS runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --from=builder /app /app

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r nomos && useradd -r -g nomos nomos
RUN chown -R nomos:nomos /app
USER nomos

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import nomos; print('Nomos is healthy'); exit(0)" || exit 1

# Expose default port for the server
EXPOSE 8000

# Default command - can be overridden
CMD ["nomos", "--help"]
