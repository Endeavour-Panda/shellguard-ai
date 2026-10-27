FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GRADIO_ANALYTICS_ENABLED=False APP_HOST=0.0.0.0 APP_PORT=7860
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser app.py ./
COPY --chown=appuser:appuser src ./src
USER appuser
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=4)"
CMD ["python", "app.py"]
