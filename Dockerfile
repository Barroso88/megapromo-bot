FROM python:3.12-slim

# Instala fontes DejaVu e Tesseract OCR para reconhecimento de preços na imagem
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código fonte
COPY src ./src

ENV PYTHONPATH=/app/src
ENV TELEGRAM_SESSION_PATH=/app/data/dealbot.session
ENV WEB_PORT=8080

EXPOSE 8080

# Volume para persistir o estado e o ficheiro da sessão no Unraid
VOLUME ["/app/data"]

CMD ["python", "-m", "dealbot.listener"]
