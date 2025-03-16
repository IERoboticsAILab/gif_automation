# app/Dockerfile

FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including FFmpeg and gifsicle for optimal performance
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gifsicle \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY requirements.txt .
COPY main.py .
COPY app.py .
COPY README.md .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose the Streamlit port
EXPOSE 8501

# Health check to verify the application is running
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run the Streamlit app
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
