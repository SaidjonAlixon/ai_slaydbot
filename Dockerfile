FROM python:3.11-slim

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

# Expose port (if needed)
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
