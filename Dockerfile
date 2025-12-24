# ----------------------------
# Base image
# ----------------------------
FROM python:3.11-slim

# ----------------------------
# Environment settings
# ----------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ----------------------------
# System dependencies
# ----------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Working directory
# ----------------------------
WORKDIR /app

# ----------------------------
# Install Python dependencies
# (done first for caching)
# ----------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ----------------------------
# Copy application code
# ----------------------------
COPY src ./src
COPY langgraph.json .
COPY README.md .

# ----------------------------
# Expose port
# ----------------------------
EXPOSE 8000

# ----------------------------
# Start FastAPI (production)
# ----------------------------
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
