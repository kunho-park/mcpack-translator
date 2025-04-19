# app/Dockerfile

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/kunho-park/mcpack-translator .

RUN uv sync

EXPOSE 7860

ENV GRADIO_SERVER_NAME="0.0.0.0"

ENTRYPOINT ["uv", "run", "python", "gradio_app.py"]
