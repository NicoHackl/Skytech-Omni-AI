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

# Feste Fassungen der beiden Befehlszeilen: eine neue Hauptversion kann das
# Verhalten von "claude -p" bzw. "codex exec" ändern und damit die Antworten
# des Add-ons. Die Codex-CLI bringt ein vorgebautes musl-Binary mit und gibt es
# nur für x86_64 und aarch64 — deshalb wird das Add-on nur für 64 Bit gebaut.
RUN npm install -g @anthropic-ai/claude-code@2.1.234 @openai/codex@0.147.0

# Antigravity-CLI (agy) für Google Gemini über das Google-AI-Pro-Abo (D-022):
# ein statisch gelinktes musl-Binary, rund 200 MB. Version und Prüfsumme sind
# festgenagelt, weil sich Ausgabeformat und Fehlerverhalten zwischen den
# Versionen mehrfach geändert haben. Die Adressen stammen aus den Manifesten
# unter antigravity-cli-auto-updater-974169037036.us-central1.run.app; der
# Ordner der arm64-Datei heißt dort tatsächlich "linux-arm-musl". Stimmt die
# Prüfsumme nicht, bricht der Bau ab. Beim Anheben der Version beide Summen neu
# aus dem Manifest holen und die Handprüfung aus docs/adr/D-022 wiederholen.
# Die CLI aktualisiert sich sonst selbst; das schaltet die Variable ab.
ENV AGY_CLI_DISABLE_AUTO_UPDATE=true
RUN set -eu; \
    base="https://storage.googleapis.com/antigravity-public/antigravity-cli/1.4.8-5447777392656384"; \
    case "$(uname -m)" in \
      x86_64) \
        url="$base/linux-x64-musl/cli_linux_x64_musl.tar.gz"; \
        sha="8a3696428a888cb44126979a9e1178c07470133351f87a4d5a7c103bab2d499462b36f1dc041681c09ed23b775ad3ac6120d13ce81d4d52902246d17cc19063e" ;; \
      aarch64) \
        url="$base/linux-arm-musl/cli_linux_arm64_musl.tar.gz"; \
        sha="dcf9e593e3947c8546f0b3f7a5ce11f83556c0e23de810f039b20ee6d50cb56dec60d43efec7409291bde25a580ad8863f8b37f215a1770cbf9ec1b75486b2d2" ;; \
      *) echo "Architektur nicht unterstützt: $(uname -m)" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/agy.tar.gz "$url"; \
    echo "$sha  /tmp/agy.tar.gz" | sha512sum -c -; \
    tar -xzf /tmp/agy.tar.gz -C /tmp antigravity; \
    install -m 0755 /tmp/antigravity /usr/local/bin/agy; \
    rm -f /tmp/agy.tar.gz /tmp/antigravity

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
COPY api_v1.py ./api_v1.py
COPY runs.py ./runs.py
COPY embeddings.py ./embeddings.py
COPY config_loader.py ./config_loader.py
COPY settings.py ./settings.py
COPY supervisor_client.py ./supervisor_client.py
COPY providers ./providers

EXPOSE 8000

# Der Supervisor startet das Add-on neu, wenn Docker es als "unhealthy" meldet
# (Ersatz für den früheren "watchdog" in config.yaml). curl bringt das
# Basisimage mit. "|| exit 1", weil Docker nur 0 und 1 als Ergebnis kennt —
# curl meldet einen Fehler mit eigenen Codes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["sh", "-c", "curl -fsS http://127.0.0.1:8000/health || exit 1"]

# Das Basisimage startet über s6-overlay (/init), und das reicht den CMD mit
# bereinigter Umgebung weiter: ohne with-contenv fehlen dem Prozess sowohl
# SUPERVISOR_TOKEN (Seite „Einstellungen“ kann nicht speichern) als auch das
# TZ von oben (Log-Zeitstempel in UTC). with-contenv lädt die Umgebung des
# Containers, die s6 beim Start beiseitegelegt hat.
CMD ["/usr/bin/with-contenv", "/opt/venv/bin/python3", "/app/app.py"]
