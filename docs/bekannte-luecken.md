# Bekannte Lücken und Stolpersteine

**Vor jeder Annahme lesen.** Diese Datei existiert, weil Doku und Code auseinanderlaufen. Steht
etwas in [architektur.md](architektur.md), heißt das nicht, dass es implementiert ist — hier steht,
wo nicht.

## Abweichungen Spec ↔ Code

| Thema | Doku sagt | Code macht | Folge für die Arbeit |
|---|---|---|---|
| API-Pfade | [frontend.md](frontend.md) beschreibt `/api/…` als Präfix | Die Endpunkte heißen `/ask`, `/models`, `/status`, `/health` ohne Präfix | Bewusst so, D-010. Beim Anlegen eines neuen Endpunkts kein `/api` voranstellen |
| Auslieferung | [frontend.md](frontend.md) nennt einen Webserver mit SPA-Fallback | Flask liefert das Bündel selbst aus | Bewusst so, D-009. Kein nginx im Bild |

## Stolpersteine

- **Der Build-Kontext ist der Add-on-Ordner, nicht die Repo-Wurzel.** Eine Datei, die im
  `Dockerfile` mit `COPY` geholt wird, muss unter `skytech_omniai/` liegen. Deshalb steht `web/`
  dort und nicht in der Wurzel. Ein `COPY ../etwas` schlägt beim Supervisor fehl, auch wenn es
  lokal mit anderem Kontext funktioniert hat.
- **Der Ingress-Pfad wechselt mit jeder Sitzung.** Wer die `index.html` zwischenspeichern lässt
  oder einen absoluten Pfad im Bündel erzeugt, bekommt beim nächsten Öffnen eine leere Seite.
  Deshalb `base: './'` und `Cache-Control: no-store`.
- **Ohne Freigabe hat die CLI keine Werkzeuge — auch keine Websuche.** Im Modus `claude -p`
  gibt es keine interaktive Rückfrage, und was nicht ausdrücklich freigegeben ist, wird
  automatisch abgelehnt. Meldet das Modell, es könne nichts nachschlagen oder `WebFetch` sei
  unterbunden, ist **nichts blockiert** — es ist nur nichts freigegeben. Zuständig ist die Option
  `tool_access` (siehe [konfiguration.md](konfiguration.md)), nicht der Prompt.
- **Die Claude-CLI liest Projektkontext aus dem Arbeitsverzeichnis.** Läuft sie im Quellbaum,
  findet sie eine `CLAUDE.md` und deutet die Anfrage als Programmieraufgabe um. Sie wird deshalb
  ausdrücklich mit `cwd="/data"` gestartet — diese Zeile nicht wegoptimieren.
- **Die CLI hängt ihren Zustand an `HOME`, nicht an `XDG_CONFIG_HOME`.** Ein früherer Versuch über
  `XDG_CONFIG_HOME=/data` hatte keinerlei Wirkung; die Anmeldung war nach jedem Neustart weg.
- **Die Codex-CLI schreibt ihre Anmeldung zurück.** Sie erneuert die Tokens im Betrieb und legt sie
  wieder unter `$CODEX_HOME/auth.json` ab. Der Wert aus der Option `codex_auth_json` darf diese
  Datei deshalb nur überschreiben, wenn er sich geändert hat — die Marke `.seed` daneben hält den
  Fingerabdruck des zuletzt übernommenen Werts. Wer diese Prüfung wegoptimiert, bekommt eine
  Anmeldung, die nach Ablauf der Ersttokens tot ist.
- **Auch die Codex-CLI liest Projektkontext aus dem Arbeitsverzeichnis** — dort heißt die Datei
  `AGENTS.md`. Sie wird deshalb mit `--cd /data` gestartet.
- **`--search` gehört vor `exec`, nicht dahinter.** Den Schalter kennt nur der Hauptbefehl;
  `codex exec --search` bricht mit „unexpected argument“ ab. Deshalb stehen Sandbox-Stufe und
  Websuche-Schalter im Aufruf **vor** dem Unterbefehl. Ein Test hält diese Reihenfolge fest.
- **`codex exec` kennt kein `--append-system-prompt`.** Die Rolle „JSON-Endpunkt“ wird dem Prompt
  vorangestellt. Wer sie in ein eigenes Feld verschieben will, findet keines.
- **Das Auswahlfeld `model` ist für alle Anbieter dasselbe.** Steht dort ein Claude-Alias und der
  Anbieter ist auf Gemini oder ChatGPT gestellt, lehnt der Provider die Anfrage ab — mit einer
  Meldung, die die gültigen Werte nennt. Das ist gewollt und kein Bug.

## Offene Bugs

| Thema | Auswirkung | Umgehung |
|---|---|---|
| Port 8000 ist unauthentifiziert | Wer den Port erreicht, kann Anfragen stellen und Kontingent verbrauchen | Port nicht ins Internet weiterleiten; wer nur die Oberfläche braucht, kann `ports` aus `config.yaml` entfernen und ausschließlich den Ingress nutzen |
| Werkzeugstufe `full` zusammen mit dem offenen Port | Ein Prompt von außen kann Befehle im Container ausführen und käme damit an das Token unter `/data` | Bei `full` den Port schließen und nur den Ingress nutzen. Vorgabe ist `web`, dort tritt der Fall nicht auf — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md) |
| Googles Schrittformat ist nicht zugesichert | Benennt Google die Schritttypen um, findet `_extract_text` den Text nicht mehr am erwarteten Ort | Ein Notfallpfad sammelt dann alles ein, was Text enthält. Bleibt auch das leer, kommt eine verständliche Meldung statt eines Absturzes |
| Die Pfade über die Befehlszeilen sind nur mit Attrappe getestet | Ein Verhaltenswechsel von `claude -p` oder `codex exec` fällt in den Tests nicht auf | Nach jedem Anheben einer CLI-Version einmal von Hand eine Anfrage über den betroffenen Anbieter stellen |
| Stufe `web` ist bei ChatGPT weiter gefasst als bei Claude | `--sandbox read-only` verhindert Schreiben und eigene Netzverbindungen, lesende Befehle im Container aber nicht | Wer das ausschließen will, stellt `tool_access` auf `off` oder nutzt `claude_sub` — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md) |

## Bewusst nicht umgesetzt

| Thema | Warum nicht | Verweis |
|---|---|---|
| Authentifizierung des offenen Ports | Automatisierungen in Home Assistant bräuchten dann ein zusätzliches Token; der Nutzen steht im Heimnetz nicht dafür | [roadmap.md](roadmap.md) |
| Verlauf über mehrere Anfragen | Jede Anfrage steht für sich. Ein Verlauf hieße Persistenz und ein Datenschutzthema, das keiner gefordert hat | [architektur.md](architektur.md) |
| Lokale Modelle über Ollama | Die Fabrik ist darauf vorbereitet, der Bedarf war bisher nicht da | [roadmap.md](roadmap.md) |
| Geräte-Anmeldung für ChatGPT in der Oberfläche | Der Zugang wird einmalig eingefügt; ein eigener Anmeldevorgang lohnt für einen einmaligen Schritt nicht | D-013 |
| 32-Bit-Architekturen | Die Codex-CLI gibt es nur für x86_64 und aarch64 | D-014 |
| Antwort gegen ein Schema prüfen | Das Add-on weiß nicht, welche Form der Aufrufer erwartet | — |

---

Wird ein Punkt behoben, wird er hier **gelöscht** und im [CHANGELOG.md](../CHANGELOG.md) vermerkt.
Eine Liste voller erledigter Einträge liest niemand mehr.
