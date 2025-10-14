# Backend Dockerfile for Universal MCP Client
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    curl \
    git \
    libpq-dev \
    postgresql-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install uv

# Copy env
COPY .env.local .env
# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies as root
RUN uv sync --frozen

# Copy application code
COPY . .

# Create a non-root user with home directory and set proper ownership
RUN groupadd -r myappgroup && \
    useradd --no-log-init -r -g myappgroup -m -d /home/myappuser myappuser && \
    chown -R myappuser:myappgroup /app && \
    mkdir -p /home/myappuser/.cache && \
    chown -R myappuser:myappgroup /home/myappuser

# Expose port (will be set by environment variable)
ARG PORT=9000
EXPOSE ${PORT}

# Switch to non-root user
USER myappuser

# Set default port
ENV PORT=${PORT}

# Run the application (port set via environment variable)
CMD uv run uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT}
