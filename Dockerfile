FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn

COPY pipeline/ pipeline/
COPY web/ web/
COPY prompts/ prompts/

# Daten (kunden/, laeufe/, sperrliste-global.yaml, users.yaml) kommen als
# Volume nach /daten - Schluessel als echte Umgebungsvariablen via env_file
# (siehe deploy/docker-compose.coldmail.yml). Kein .env im Image.
ENV DATEN_DIR=/daten

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
