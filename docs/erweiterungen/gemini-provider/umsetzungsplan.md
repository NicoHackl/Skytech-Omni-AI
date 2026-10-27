# Umsetzungsplan

Zwei Spuren, unabhängig voneinander. **Spur 1 ist empfohlen und kann sofort beginnen.** Spur 2 ist
an Schranken gebunden und beginnt erst nach der Entscheidung des Users
([abo-weg-antigravity.md](abo-weg-antigravity.md), Schranken G1 bis G3).

## Rahmen für jedes Arbeitspaket

Die Regeln stehen in [`../../../AGENTS.md`](../../../AGENTS.md) und werden hier nicht wiederholt. Was für
dieses Vorhaben davon zählt:

| Regel | Folge hier |
|---|---|
| Git (Regel 1) | Arbeit auf `agent/main`. **Jeder Push mit Änderung unter `skytech_omniai/` ist ein Release an alle Nutzer** (D-017). Spur 2 deshalb auf `feature/gemini-sub`, bis sie am echten Gerät geprüft ist |
| Changelog (Regel 4) | Trailer `Changelog-<Kategorie>:` aus Nutzersicht, nur bei nutzerrelevanter Änderung |
| Doku (Regel 5) | Betroffene `docs/`-Dateien im selben Arbeitspaket, keine Nachreichung |
| Nicht raten (Regel 7) | Die mit „ungeprüft“ markierten Punkte sind Prüfaufträge, keine Annahmen |
| Oberfläche (Regeln 8, 10, 11) | Nur bestehende Komponenten und Klassen; Designsprache Home Assistant (`data-design="ha"`) |
| Nur zeigen, was betrifft (Regel 12) | Meldungen ohne Statuscodes, Pfade, Klassennamen, Rohausgabe |
| Tests | Ohne Netz und ohne echte Zugänge: `urlopen` und `subprocess.run` ersetzen. Pflichtfälle Normal, Fehler, Leer; für Meldungen zusätzlich „keine Technik im Text“ ([../../test-strategie.md](../../test-strategie.md)) |
| Prüfung | `scripts/check.sh` vor jedem Commit; bei Änderungen am Dockerfile zusätzlich `scripts/check.sh --docker` |

## Spur 1 — API-Weg (empfohlen)

Ziel: `gemini` zeitgemäß machen, ohne neue Abhängigkeit und ohne Eingriff in die gemeinsame
Schnittstelle. Hintergründe und Zahlen: [api-weg.md](api-weg.md).

| AP | Inhalt | Abhängig von |
|---|---|---|
| 1-0 | Entscheidungen 2 und 3 aus [README.md](README.md#entscheidungen-die-beim-user-liegen) einholen; Handprüfungen H1 und H6 mit eigenem Schlüssel | — |
| 1-1 | Modellliste ergänzen | 1-0 (H1) |
| 1-2 | Werkzeugstufe für Gemini (`url_context`) | 1-0 (H3, H4) |
| 1-3 | Fehlermeldungen für Abrechnungs- und Werkzeugfälle | 1-2 (H5) |
| 1-4 | optional: Schema durchreichen, Nutzungsdaten | 1-0 (H6), eigener Beschluss |
| 1-5 | nur bei Entscheidung 2 = ja: Schalter für die Websuche | 1-2 |
| 1-6 | Doku- und Roadmap-Abschluss | alle |

### AP 1-1 — Modellliste ergänzen

- **Code:** `GEMINI_MODELS` in `providers/gemini_provider.py` um `gemini-4-argon` und
  `gemini-3.8-flash` ergänzen, Reihenfolge = Anzeigereihenfolge (empfohlene zuerst, `2.5`-Modelle ans
  Ende). `DEFAULT_MODEL` nach Entscheidung 3. **Nichts entfernen** (Begründung in
  [api-weg.md](api-weg.md#21-die-modellliste-ist-veraltet)).
- **Konfiguration:** `schema.model` in `skytech_omniai/config.yaml` um dieselben Werte erweitern.
- **Texte:** Tabelle „Verfügbare Gemini-Modelle“ in `skytech_omniai/info.md`; Beschreibungen ohne Preise.
- **Tests:** Der Konsistenztest `test_model_list_matches_the_providers` schlägt an, wenn eine
  der beiden Stellen vergessen wird. In `test_gemini_provider.py` einen Test, der die neuen
  Kennungen ohne Fehler auflöst.
- **Commit:** `feat(gemini): Gemini 4 Argon und Gemini 3.8 Flash zur Auswahl hinzugefügt`
  mit `Changelog-Hinzugefügt: Google Gemini 4 Argon und Gemini 3.8 Flash stehen zur Auswahl.`
- **Abnahme:** `/models` nennt beide; ein Lauf mit `gemini-3.8-flash` liefert JSON (H2).

### AP 1-2 — Werkzeugstufe für Gemini

- **Code:** In `GeminiProvider.execute` die Stufe über `resolve_tool_access()` auflösen (liegt in
  `base_provider.py`) und in `tools` übersetzen: `off` → keine; `web` und `full` →
  `[{"type": "url_context"}]`. Bei aktiven Werkzeugen den englischen Absatz zur Systemanweisung
  ergänzen. Eine Logzeile mit der Stufe, wie bei Claude und Codex. Rückfall aus H4 (ohne
  `response_format` bei Werkzeugen) einbauen, falls nötig.
- **Verhaltensänderung für Bestandsinstallationen:** Vorgabe ist `web`. Ab dem Update sendet
  Gemini damit `url_context` mit; Adressen im Prompt werden von Google abgerufen. Das ist
  kostenlos, aber eine sichtbare Änderung → `Changelog-Geändert:`.
- **Texte und Doku (alle im selben Paket):**
  - `skytech_omniai/web/src/pages/Einstellungen.tsx`: Hinweis unter „Werkzeuge“ („Gilt für Claude und
    ChatGPT; Gemini antwortet immer aus seinem Wissen.“) → neue Aussage: Gemini ruft nur Adressen
    ab, die im Prompt stehen. Nur Text, kein neues Bauteil.
  - `skytech_omniai/info.md`: Absatz „`tool_access` betrifft `claude_sub` und `codex_sub`. Google
    Gemini hat keinen Web-Zugriff …“.
  - [../../konfiguration.md](../../konfiguration.md), Abschnitt „Werkzeuge der Befehlszeilen“, letzter Absatz.
  - [../../sicherheit-datenschutz.md](../../sicherheit-datenschutz.md): Tabelle „Werkzeuge der Befehlszeilen“ (Gemini: nur
    Abruf von Adressen im Prompt, Google führt ihn aus), Tabelle „Externe Dienste“ (Google bekommt
    zusätzlich die abgerufenen Adressen).
  - [../../architektur.md](../../architektur.md): Zeile „Anbieter Gemini“ erwähnt keine Werkzeuge — prüfen.
- **Tests:** `execute` mit ersetztem `urlopen`, der den Rumpf mitschneidet: je Stufe das erwartete
  `tools`; `full` gleich `web`; Zusatzabsatz nur mit Werkzeugen; kein Schlüssel im Log.
- **Commit:** `feat(gemini): Werkzeugstufe auch für Gemini (Seitenabruf)`.
- **Abnahme:** H3 und H4 bestanden.

### AP 1-3 — Fehlermeldungen

- Aufzeichnung der echten Antworten aus H5 (Code und Text von Google), als feste Testdaten ablegen.
- `HTTP_FEHLERTEXTE` bzw. `_http_fehler` um die Fälle aus [api-weg.md](api-weg.md#3-fehlermeldungen)
  erweitern. Trennung nach Fall nur, wenn Google sie am Antwortinhalt unterscheidbar macht; sonst
  ein Satz mit beiden Hinweisen.
- **Tests:** je Fall die Meldung; jeder Satz ohne Antwortcode, Klassennamen und Rohtext von Google.
- **Commit:** `fix(gemini): verständliche Meldung bei fehlender Abrechnung`.

### AP 1-4 — optional: Schema und Nutzungsdaten

Eigener Beschluss, weil es die gemeinsame Schnittstelle berührt (D-005):

- **Schema durchreichen:** `execute` bekäme einen optionalen Parameter; `api_v1.py` reicht das
  Schema der Anfrage durch. Rückwärtskompatibel, die Prüfung mit `jsonschema` bleibt (D-020).
- **Nutzungsdaten:** `usage` aus der Antwort als Attribut der (je Anfrage neuen) Provider-Instanz
  ablegen; `api_v1.py` liest es und füllt das Feld, das [../../roadmap.md](../../roadmap.md) (M5) als offen führt.
- Beides nur, wenn Skytech X es braucht. Vertrag: [../../contracts/omniai-api-v1.yaml](../../contracts/omniai-api-v1.yaml)
  ist eine Kopie, Änderungen zuerst im Repo Skytech-X-Backend.

### AP 1-5 — nur bei Entscheidung 2 = ja: Websuche

- Neue Option (Schalter) statt neuer Stufe, Vorgabe aus. Schema, `OPTION_ENV_MAP`, Einstellungsseite,
  `GET /settings`, Oberfläche, Tests nach dem Muster einer bestehenden Option.
- Hinweis an der Option: Abrechnung nötig, Google-Auflagen (Anzeige der Suchvorschläge,
  Auswertungsverbot) in einem Satz.
- Zusätzlicher Eintrag in [../../bekannte-luecken.md](../../bekannte-luecken.md): „Bedingungen von Google zur Websuche
  sind für Automationen nicht erkennbar erfüllbar.“

### AP 1-6 — Abschluss

- [../../roadmap.md](../../roadmap.md): M2 „Google Gemini“ ergänzen um „Modelle und Werkzeuge aktualisiert“, bzw.
  Punkte der Pakete mit Status eintragen.
- [../../bekannte-luecken.md](../../bekannte-luecken.md): Zeile „Googles Schrittformat ist nicht zugesichert“ prüfen;
  neu: Modelle mit eingeschränktem Zugang.
- Entscheidung als **D-022** eintragen ([adr-entwurf.md](adr-entwurf.md)).
- Dieser Ordner wird danach auf den umgesetzten Teil gekürzt oder gelöscht (Pflegeregel:
  keine Plan-Dateien stehen lassen, die der Code überholt hat).

## Spur 2 — Abo-Weg (nur nach Freigabe)

Voraussetzung: G1 bis G3. Ohne sie wird kein Arbeitspaket dieser Spur begonnen.

| AP | Inhalt |
|---|---|
| S-0 | Spike am echten Konto ([spike-abo-anmeldung.md](spike-abo-anmeldung.md)); Ergebnis in die Tabelle dort eintragen. **Kein Code im Repo.** Bestanden = Schranke G2 |
| S-1 | ADR D-022 (Annahme des Risikos) und D-023 (Anmeldeverfahren nach Spike) schreiben, `feature/gemini-sub` anlegen |
| S-2 | Provider `providers/gemini_sub_provider.py` samt Tests nach [abo-weg-antigravity.md](abo-weg-antigravity.md), Abschnitt 5 |
| S-3 | Bild: Installation der CLI (festgenagelt), Rechte, `AGY_CLI_DISABLE_AUTO_UPDATE`; `scripts/check.sh --docker` auf **beiden** Architekturen (aarch64 wird in der CI nicht gebaut, siehe [../../bekannte-luecken.md](../../bekannte-luecken.md)) |
| S-4 | Konfiguration und Einstellungsseite: Option `gemini_auth_json`, Modelle, Prüfung des Werts |
| S-5 | Schnittstellen: `/models`, `/status`, `/v1/capabilities` |
| S-6 | Doku-Abschluss, Hinweis auf das Risiko an jeder Stelle, an der der Provider auswählbar ist |
| S-7 | Handabnahme am echten Home Assistant, erst dann Merge nach `agent/main` |

### Berührungspunkte (Stand des Codes am 27.10.2026, nach dem Muster von `codex_sub`)

| Datei | Änderung |
|---|---|
| `skytech_omniai/providers/gemini_sub_provider.py` | **neu**: Provider, Modellliste, Meldungen, Zugang ablegen, Aufruf, Aufräumen |
| `skytech_omniai/providers/factory.py` | `_PROVIDERS` und `_ANZEIGENAMEN` |
| `skytech_omniai/config_loader.py` | `OPTION_ENV_MAP` (`gemini_auth_json` → `GEMINI_AUTH_JSON`), `SECRET_OPTIONS` |
| `skytech_omniai/config.yaml` | `options`, `schema` (Passwortfeld), `provider`-Liste, `model`-Liste (Konsistenztest!), Beschreibung |
| `skytech_omniai/settings.py` | Modelle je Anbieter, Prüfung des eingefügten Werts (wie `codex_auth_json`) |
| `skytech_omniai/app.py` | `/models`, `/status` (`credentials`) |
| `skytech_omniai/api_v1.py` | `PROVIDERS`, `credentials_present`; `TOOL_PROVIDERS` bleibt unverändert |
| `skytech_omniai/Dockerfile` | Installationsblock; `COPY providers` deckt die neue Datei ab |
| `skytech_omniai/web/src/types.ts`, `provider.ts` | `ProviderName`, Optionsschlüssel, Anzeigename |
| `skytech_omniai/web/src/pages/Dashboard.tsx` | `CREDENTIAL_KEYS` |
| `skytech_omniai/web/src/pages/Einstellungen.tsx` | Eingabefeld für den Zugang mit Risikohinweis |
| `skytech_omniai/info.md`, `README.md` | Einrichtung, Risiko |
| `tests/conftest.py` | neue Umgebungsvariablen vor jedem Test abräumen |
| `tests/unit/providers/test_gemini_sub_provider.py` | **neu**, mit ersetztem `subprocess.run` |
| `tests/unit/providers/test_factory.py`, `test_addon_config.py`, `test_api_v1.py`, `test_app.py`, `test_config_loader.py`, `test_settings.py` | je der neue Anbieter |
| `docs/` | `architektur.md` (Tabelle, Diagramm), `konfiguration.md`, `api-referenz.md`, `sicherheit-datenschutz.md` (Datenarten, externe Dienste, Verlauf auf der Platte), `bekannte-luecken.md`, `roadmap.md`, `design-entscheidungen.md`, `adr/` |
| `docs/contracts/omniai-api-v1.yaml` | `provider` ist dort eine offene Menge; Beschreibung nur prüfen. Master liegt im Repo Skytech-X-Backend |

Voraussichtlich braucht die Oberfläche keine neuen Komponenten oder Klassen. Das ist beim Bau
gegen [../../frontend.md](../../frontend.md) und [../../design-system.md](../../design-system.md) zu prüfen
(eiserne Regel 8) — hier ist es nicht belegt.

## Reihenfolge und Aufwand (grobe Schätzung)

| Block | Aufwand | Anmerkung |
|---|---|---|
| 1-0 Entscheidungen, Handprüfung H1/H6 | 1 Stunde | braucht einen AI-Studio-Schlüssel |
| 1-1 bis 1-3 | 0,5 bis 1 Tag | Wartezeit nur für H5 (Freikontingent-Schlüssel) |
| 1-4, 1-5 | je 0,5 Tag | nur bei Bedarf |
| 1-6 | 1 Stunde | |
| S-0 Spike | 0,5 Tag | Konto, Browser, Docker |
| S-1 bis S-7 | 3 bis 5 Tage | davon der Großteil Bild, Anmeldung und Aufräumen |

## Nicht Teil des Plans

- Der Weg über den ausgelesenen Abo-Token gegen die Cloud-Code-Schnittstelle (Weg E in
  [recherche.md](recherche.md#5-vergleich-aller-wege)) — ausdrücklich untersagt.
- Gemini CLI oder `agy` mit API-Schlüssel statt direktem Aufruf (Weg D) — kein Gewinn.
- Werkzeuge in Agent-Läufen für Gemini (`runs.py`, D-021): die Interactions-API kennt
  Funktionsaufrufe, aber das ist ein eigenes Vorhaben ([../../roadmap.md](../../roadmap.md), M5).
