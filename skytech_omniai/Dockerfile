ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM $BUILD_FROM

# Zeitzone der Log-Ausgaben. Ohne tzdata liefe der Container in UTC und die
# Zeitstempel im Log wären falsch (eiserne Regel 9 in AGENTS.md).
ENV TZ=Europe/Berlin

RUN apk add --no-cache \
    nodejs \
    npm \
    python3 \
    py3-pip \
    py3-virtualenv \
    bash \
    tzdata

# Feste Fassung der Claude-Code-CLI: eine neue Hauptversion kann das Verhalten
# von "claude -p" ändern und damit die Antworten des Add-ons.
RUN npm install -g @anthropic-ai/claude-code@2.1.234

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Die Oberfläche wird hier gebaut und nicht in einer eigenen Bauphase: Node und
# npm sind für die Claude-CLI ohnehin im Bild, und ein zweites Basisimage gibt
# es nicht für jede Architektur, für die dieses Add-on gebaut wird.
# Erst die Abhängigkeitsliste kopieren, damit die Installation im Cache bleibt,
# solange sich nur der Quellcode ändert.
COPY web/package.json web/package-lock.json ./web/
RUN npm ci --prefix /app/web
COPY web ./web
RUN npm run build --prefix /app/web \
    && rm -rf /app/web/node_modules /app/web/src /root/.npm

COPY config.yaml ./config.yaml
COPY app.py ./app.py
COPY config_loader.py ./config_loader.py
COPY providers ./providers

EXPOSE 8000

CMD ["/opt/venv/bin/python3", "/app/app.py"]
