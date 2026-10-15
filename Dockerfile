FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NFC_HOST=0.0.0.0 \
    PORT=8001 \
    NFC_DB_PATH=/data/counts.sqlite3

WORKDIR /app
RUN useradd --uid 10001 --create-home nfc \
    && mkdir /data && chown nfc:nfc /data
COPY --chown=nfc:nfc server.py index.html app.js styles.css ./
USER nfc
EXPOSE 8001
CMD ["python3", "server.py"]
