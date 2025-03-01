FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY robofuse.py .
COPY ui_utils.py .
COPY config.json .

# Create directories for output and cache
RUN mkdir -p /data/output
RUN mkdir -p /data/cache

# Set volume mount points
VOLUME ["/data/output", "/data/cache", "/app/config.json"]

# Set default command to run in watch mode with summary output
CMD ["python", "robofuse.py", "--watch", "--summary"] 