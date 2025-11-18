# Dockerfile for secure sandbox execution environment
# Minimal Python image with security hardening

FROM python:3.11-slim

# Security: Run as non-root user
RUN groupadd -r sandbox && useradd -r -g sandbox sandbox

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /sandbox

# Set proper permissions
RUN chown -R sandbox:sandbox /sandbox

# Switch to non-root user
USER sandbox

# Default command (will be overridden)
CMD ["/bin/sh"]
