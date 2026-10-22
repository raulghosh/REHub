FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home app
USER app
ENV PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sfr-eval", "serve", "--host", "0.0.0.0"]
