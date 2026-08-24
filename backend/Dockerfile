# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy all project files
COPY . .

# Debug: list contents of /app
RUN ls -la /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt && \
    # Fix for Razorpay/pkg_resources compatibility
    # Newer setuptools versions don't expose pkg_resources as a top-level module
    # Create symlink to pip's vendored version if needed
    [ ! -d "/usr/local/lib/python3.11/site-packages/pkg_resources" ] && ln -sf pip/_vendor/pkg_resources /usr/local/lib/python3.11/site-packages/pkg_resources || true

# Production stage
FROM python:3.11-slim AS production

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code preserving directory structure
COPY --from=builder /app/backend ./backend
COPY --from=builder /app/scripts ./scripts
COPY --from=builder /app/tests ./tests

# Copy seeding script and entrypoint
COPY create_human_approval_scenario.py /app/create_human_approval_scenario.py
COPY backend/docker-entrypoint.sh /app/docker-entrypoint.sh

# Change ownership of app directory to non-root user
RUN chown -R appuser:appgroup /app && \
    chmod +x /app/docker-entrypoint.sh

# Set PYTHONPATH to include both root and backend to resolve 'scripts' and 'app' imports
ENV PYTHONPATH=/app:/app/backend

# Change to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application with entrypoint script for seeding
ENTRYPOINT ["/app/docker-entrypoint.sh"]