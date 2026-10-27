# Erweiterung: Gemini-Provider mit Google-AI-Pro-Abo

> **Stand: Recherche abgeschlossen am 27.10.2026. Nichts davon ist umgesetzt.** Dieser Ordner
> beschreibt Geplantes und Befunde, keinen Ist-Stand. Was das Add-on heute tut, steht in
> [../../architektur.md](../../architektur.md); Abweichungen davon in
> [../../bekannte-luecken.md](../../bekannte-luecken.md).

## Auftrag

Die Gemini-Modelle über das **Google-AI-Pro-Abo** nutzen — wie bei `claude_sub` und `codex_sub`
über das Abo statt über einen nach Verbrauch abgerechneten Schlüssel — und das so, dass es in die
bestehende Provider-Struktur passt (D-005).

## Ergebnis in Kürze

1. **Der naheliegende Weg ist weg.** Die Gemini CLI bedient Google-AI-Pro-Konten seit dem
   18.06.2026 nicht mehr. Nachfolger für Abo-Nutzer ist die **Antigravity CLI** (`agy`).
2. **Technisch ginge es.** `agy -p --output-format json` ist ein Headless-Modus wie `claude -p`.
   Für Alpine/musl gibt es ein Binary; es läuft auf dem Basisimage des Add-ons (am 27.10.2026
   selbst geprüft). Die Anmeldung per Google-Konto lässt sich im Container aber **nicht
   verlässlich** halten — das ist ungeklärt und fehleranfällig, siehe
   [abo-weg-antigravity.md](abo-weg-antigravity.md).
3. **Google schließt genau diesen Einsatz für Privatabos aus.** Die offizielle FAQ der
   Antigravity CLI sagt sinngemäß: Der Headless-Modus ist für direktes Scripting und CI gedacht;
   `agy` in Anwendungen einzupacken wird **unter Verbraucherplänen nicht unterstützt** (englischer
   Wortlaut und Quelle in [recherche.md](recherche.md#die-entscheidende-klausel)). OmniAI ist
   genau so eine Anwendung: eine HTTP-Brücke, die Anfragen von Home Assistant und Skytech X an
   das Modell weiterreicht. Die Bedingungen nennen als Folge von Fremdwerkzeugen die Sperrung des
   Kontos.
4. **Der von Google für Fremdanwendungen vorgesehene Weg ist der API-Schlüssel.** Den hat das
   Add-on schon (`gemini`, D-007). Das Abo selbst lässt sich darüber **nicht** anzapfen; Google
   AI Pro bringt hier nur einen Cloud-Guthabenvorteil und das Freikontingent der Flash-Modelle.
5. **Der vorhandene Gemini-Provider ist veraltet und hat keine Werkzeuge.** Die Modellliste
   kennt `gemini-4-argon` und `gemini-3.8-flash` nicht, und `tool_access` wirkt bei Gemini
   nicht, obwohl die API Seitenabruf (`url_context`, kostenlos) und Websuche (`google_search`)
   anbietet. Die Websuche hat Auflagen, die zu einer Brücke für Automationen schlecht passen
   (Anzeigepflicht für Suchvorschläge, Auswertungsverbot) — Details in [api-weg.md](api-weg.md#22-werkzeuge-die-api-kann-mehr-als-das-add-on-nutzt).

## Empfehlung

| Spur | Inhalt | Empfehlung |
|---|---|---|
| **1 — API-Weg ausbauen** | Modellliste aktualisieren, `tool_access` über `url_context` abbilden, Fehlertexte nachziehen, optional Nutzungsdaten und Schema. Alles unterstützt, ohne neue Abhängigkeit im Bild | **Umsetzen** — [api-weg.md](api-weg.md) |
| **2 — Abo-Weg über `agy`** | Neuer Provider `gemini_sub` nach dem Muster von D-013 | **Zurückstellen.** Nur nach ausdrücklicher Entscheidung des Users und bestandenem Spike — [abo-weg-antigravity.md](abo-weg-antigravity.md), [spike-abo-anmeldung.md](spike-abo-anmeldung.md) |

Reihenfolge, Arbeitspakete, Tests und Doku-Pflichten: [umsetzungsplan.md](umsetzungsplan.md).
Entscheidungsvorlage im Format der ADRs: [adr-entwurf.md](adr-entwurf.md).

## Entscheidungen, die beim User liegen

1. **Abo-Weg: ja oder nein?** Die Empfehlung ist nein (Zurückstellen). Wer ihn trotzdem will,
   trägt das Risiko, dass Google das Konto für Antigravity bzw. die Gemini CLI sperrt, und muss
   wissen, dass ein veröffentlichter Provider dieses Risiko an **alle** Nutzer des Add-ons
   weitergibt (jeder Push auf `agent/main` mit Änderung unter `skytech_omniai/` ist ein Release,
   siehe [../../git-workflow.md](../../git-workflow.md)).
2. **Websuche (`google_search`) bei Gemini zulassen?** Sie funktioniert nur mit Abrechnung (nicht
   im Freikontingent), kostet nach 5.000 Suchanfragen im Monat 14 US-Dollar je 1.000 und ist laut
   Googles Bedingungen daran gebunden, dass die Ergebnisse samt Suchvorschlägen dem fragenden
   Endnutzer angezeigt und nicht ausgewertet werden. Eine Brücke, deren JSON Automationen
   weiterverarbeiten, erfüllt das nicht erkennbar. Vorschlag: `web` bedeutet bei Gemini nur
   Seitenabruf (`url_context`); die Websuche kommt höchstens als eigener, ausdrücklich
   eingeschalteter Schalter.
3. **Standardmodell:** Alias `gemini-flash-latest` behalten (zeigt auf das jeweils neueste
   Flash-Modell, verändert sich ohne Zutun) oder auf `gemini-3.8-flash` festnageln.

## Nicht geprüft

- Ob die Bedingungen von Anthropic und OpenAI für den bestehenden Betrieb von `claude_sub` und
  `codex_sub` ähnliche Klauseln enthalten. Das war nicht Teil des Auftrags, liegt aber nahe.
- Das Verhalten von `agy` **nach** der Anmeldung (Modellnamen, Werkzeuge, Quotenfehler,
  Dauerhaftigkeit der Anmeldung). Es braucht ein Google-Konto und einen Browser — dafür ist
  [spike-abo-anmeldung.md](spike-abo-anmeldung.md) geschrieben.

## Dateien

| Datei | Inhalt |
|---|---|
| [recherche.md](recherche.md) | Befunde mit Quellen, Vergleich aller Wege, Googles Wortlaut |
| [abo-weg-antigravity.md](abo-weg-antigravity.md) | Steckbrief der `agy`-CLI, eigene Messungen, Risiken, Entwurf von `gemini_sub` |
| [api-weg.md](api-weg.md) | Ausbau des bestehenden Providers `gemini` (Schlüssel, Modelle, Werkzeuge, Kosten, Datenschutz) |
| [umsetzungsplan.md](umsetzungsplan.md) | Arbeitspakete beider Spuren, Berührungspunkte im Code, Tests, Doku, Changelog |
| [spike-abo-anmeldung.md](spike-abo-anmeldung.md) | Anleitung, die offenen Punkte des Abo-Wegs am echten Konto zu prüfen |
| [adr-entwurf.md](adr-entwurf.md) | Entwurf von D-022 (Status „Vorgeschlagen“) |
