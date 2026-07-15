FROM python:3.11-slim

# Evita interações do apt e garante prints não bufferizados
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependências de sistema (LibreOffice e dependências básicas)
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-java-common \
    wget \
    gnupg \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Configurar diretório de trabalho
WORKDIR /app

# Copiar requirements.txt
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalar os navegadores e dependências do Playwright
RUN playwright install --with-deps chromium

# Criar e liberar a pasta de uploads temporários
RUN mkdir -p /tmp/uploads && chmod 777 /tmp/uploads

# Copiar todo o código-fonte da aplicação
COPY . .

# Expor a porta 5000 (onde o gunicorn irá rodar)
EXPOSE 5000

# Executar a aplicação usando o Gunicorn (multi-processo para produção)
# Usaremos 2 workers, ideal para nuvem leve.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
