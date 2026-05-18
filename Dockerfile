FROM python:3.10-slim

WORKDIR /app

# Dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif
COPY . .

EXPOSE 8000

# Lance l'API FastAPI
CMD ["uvicorn", "interfaces.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
