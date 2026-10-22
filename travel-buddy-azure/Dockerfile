# ONE image, TWO jobs. The same image runs as either:
#   - the API     (default command below)
#   - the WORKER  (Azure overrides the command with:  celery -A celery_app:celery_app worker ...)
# Keeping one image means one build and one version number for both parts.
FROM python:3.12-slim

WORKDIR /app

# Install packages first (this layer is reused when only the code changes)
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# Do not run as the root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
