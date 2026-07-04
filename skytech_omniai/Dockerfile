ARG BUILD_FROM=alpine:3.19
FROM $BUILD_FROM

RUN apk add --no-cache \
    nodejs \
    npm \
    python3 \
    py3-pip \
    py3-virtualenv \
    bash

RUN npm install -g @anthropic-ai/claude-code

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN /opt/venv/bin/pip install --no-cache-dir flask

WORKDIR /app
COPY app.py ./app.py
COPY config_loader.py ./config_loader.py
COPY providers ./providers

EXPOSE 8000

CMD ["/opt/venv/bin/python3", "/app/app.py"]
