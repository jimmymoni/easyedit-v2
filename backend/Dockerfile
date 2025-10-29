FROM python:3.13-slim

WORKDIR /app

# Install system dependencies including ffmpeg for audio processing
# ffmpeg: Audio format conversion and segment extraction
# ffprobe: Audio duration detection
# libsndfile1: Audio file I/O for scipy/numpy
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    ffprobe \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for uploads, temp, and logs
RUN mkdir -p uploads temp logs

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the application
CMD ["python", "app.py"]