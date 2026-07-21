FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application code
COPY browser_worker/ ./browser_worker/

# Create checkpoint directory
RUN mkdir -p /tmp/checkpoints

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "browser_worker.worker"]
