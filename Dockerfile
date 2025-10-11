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

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uv", "run", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
