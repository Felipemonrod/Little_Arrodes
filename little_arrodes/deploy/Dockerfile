FROM python:3.11-alpine

WORKDIR /bot

# Instala dependências em uma camada separada para usar cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código modularizado (main.py, config.py, cogs/, utils/)
COPY . .

# Cria diretórios de dados e logs (serão montados como volumes)
RUN mkdir -p /bot/data /bot/logs

# Executa o ponto de entrada correto
CMD ["python", "main.py"]
