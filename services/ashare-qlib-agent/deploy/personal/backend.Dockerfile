FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY ashare_qlib_agent ./ashare_qlib_agent
COPY config.example.yaml ./config.example.yaml
COPY config.fund.example.yaml ./config.fund.example.yaml
COPY config.local-verify.yaml ./config.local-verify.yaml
COPY config.personal.example.yaml ./config.personal.example.yaml
COPY config.postgres.yaml ./config.postgres.yaml

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[api,research,storage]"

EXPOSE 8710

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8710"]

