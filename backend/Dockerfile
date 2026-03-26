FROM python:3.10-slim

WORKDIR /app
ENV PYTHONPATH=/app

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application (app, data, scripts)
COPY ./app /app/app
COPY ./data /app/data
COPY ./scripts /app/scripts
COPY ./entrypoint.sh /app/entrypoint.sh

# Windows checkouts often use CRLF; Linux then fails with "no such file or directory" on shebang
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose the FastAPI default port
EXPOSE 8000

# Invoke via sh so a bad shebang line never breaks the container
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
