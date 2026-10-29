# Vorprüfung von Gemini Web

Stand: 29.10.2026. Geprüfte Bibliothek: `gemini-webapi==2.1.1` aus dem
[PyPI-Quellarchiv](https://pypi.org/project/gemini-webapi/2.1.1/), nicht dem laufenden
Entwicklungsbranch. Veröffentlichung laut PyPI: 28.08.2026.

| Prüfung | Beleg und Grenze |
|---|---|
| S1, Alpine | Installation mit `--only-binary=:all:` und Import in den Basisimages `ghcr.io/home-assistant/aarch64-base:3.19` und `ghcr.io/home-assistant/amd64-base:3.19` erfolgreich. Kein Compiler. |
| S2, Python | Download der vollständigen Wheel-Abhängigkeiten für Python 3.11 auf beiden musl-Architekturen und Python 3.14 auf aarch64 erfolgreich. `pydantic-core` hat musllinux-1.1-Wheels; bei einer Cross-Plattform-Prüfung muss pip sowohl 1.1 als auch 1.2 berücksichtigen. |
| S3, Client halten | Eigener Thread und Clients je Konto implementiert; Wiederverwendung, Abbruch und Schließen mit Attrappe geprüft. Langzeitbetrieb mit Google offen. |
| S4, Modelle | Quelltext bestätigt `list_models()`, `model_name`, `resolve_model()` mit Aliasauflösung. Die tatsächliche Auswahl eines AI-Pro-Kontos bleibt offen. |
| S5, JSON | Gemeinsamer Parser wird benutzt. Tests prüfen JSON, leere Antwort und Prosa; Zuverlässigkeit mit Google offen. |
| S6, Limits | Eigene Fehlerklassen im Quelltext bestätigt. Kein zugesicherter Zeitpunkt für die Freigabe. Fenster- und Wochenlimit mit echtem Konto ungeprüft. |
| S7, Cookies | Hintergrund-Erneuerung und Speicherung im Quelltext bestätigt. Der Cookie-Cache benutzt standardmäßig einen Zugangswert im Dateinamen: durch kontoabhängigen Kontext und festen Dateinamen ersetzt, beide Importstellen getestet. Haltbarkeit auf dem HA-Server offen. |
| S8, temporäre Chats | `generate_content(..., temporary=True)` im Quelltext vorhanden; die Brücke setzt es bei jeder Anfrage. Wirksamkeit auf Google-Seite noch handzuprüfen. |
| S9, Anhänge | Übergabe von Dateipfaden bestätigt, private Dateien und Aufräumen auch bei Abbruch getestet. Tatsächliche Google-Grenzen bleiben offen. |
| S10, Parallelität | Alle Operationen bewusst nacheinander. Keine parallelen Google-Anfragen ausprobiert. |
| S11, Supervisor | Kein HA-Testsystem mit alter Option vorhanden. Keine Aussage, ob das Update oder erst der Start abgelehnt wird. Vor Update vorübergehend Claude wählen, danach AGY neu einstellen. |
| S12, Pflege | Die festgelegte Version erschien am 28.08.2026. Häufigkeit künftiger Web-App-Brüche und offene Fehler wurden nicht als verlässliche Betriebszusage gewertet. |

Der User führt die Handprüfung mit einem separaten Konto erst nach Installation des Updates
im HA-Add-on aus. Keine Cookies wurden an den Agenten übergeben; alle Testwerte sind Attrappen.
