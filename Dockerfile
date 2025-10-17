FROM python:3.11-slim

# Install curl for health check
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Create data directory for persistent storage
RUN mkdir -p /app/data

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy DataBase.db to the app directory (if exists)
COPY DataBase.db* /app/

# Set environment variables
ENV DATABASE_PATH=/app/DataBase.db
ENV PERSISTENT_STORAGE=true
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "main.py"]
