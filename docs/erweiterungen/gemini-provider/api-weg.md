# API-Weg: den Provider `gemini` ausbauen

> **Status: empfohlen (Spur 1), nichts umgesetzt.** Das ist der von Google für Fremdanwendungen
> vorgesehene Weg ([recherche.md](recherche.md#die-entscheidende-klausel)). Er nutzt **nicht** das
> Abo-Kontingent, aber alles, was Google AI Pro für Entwickler bereithält (Abschnitt 4).
> Arbeitspakete: [umsetzungsplan.md](umsetzungsplan.md#spur-1--api-weg-empfohlen).

## 1. Ist-Stand (aus dem Code, 27.10.2026)

| Thema | Heute | Ort |
|---|---|---|
| Schnittstelle | Interactions-API, `POST /v1beta/interactions`, `urllib` (D-007), Schlüssel als Kopfzeile `x-goog-api-key` | `providers/gemini_provider.py` |
| Modellliste | 8 Einträge, Vorgabe `gemini-flash-latest`; jede `gemini-*`-Kennung wird durchgelassen | `GEMINI_MODELS`, `_resolve_model` |
| Anfrage | `input`, `system_instruction` (nur die Rolle „JSON-Endpunkt“), `response_format` `text` + `application/json` ohne Schema, `store: false` | `execute` |
| Werkzeuge | **keine.** `tool_access` hat bei Gemini keine Wirkung ([../../konfiguration.md](../../konfiguration.md#werkzeuge-der-befehlszeilen)) | — |
| Auswertung | Text aus den Schritten vom Typ `model_output`, Notfallpfad über alle Schritte | `_extract_text` |
| Nutzungsdaten | `usage` der Antwort wird **nicht** gelesen | — |
| Fehler | Satz je Antwortcode (400, 401, 403, 404, 429, 500, 503) | `HTTP_FEHLERTEXTE` |
| Zugang | Option `gemini_api_key`, Umgebungsvariablen `GEMINI_API_KEY` (und `GOOGLE_API_KEY`) | `config_loader.py` |

## 2. Was sich geändert hat

### 2.1 Die Modellliste ist veraltet

Abgleich der Liste im Code mit der Modellübersicht von Google (Stand 27.10.2026):

| Eintrag im Code | Befund | Vorschlag |
|---|---|---|
| `gemini-flash-latest` | Alias, zeigt auf das neueste Flash-Modell; verändert sich ohne Zutun | behalten oder festnageln — Entscheidung 3 in [README.md](README.md#entscheidungen-die-beim-user-liegen) |
| *(fehlt)* `gemini-4-argon` | Flaggschiff, stabil. **Nicht im Freikontingent**; 2,00 / 10,00 US-Dollar je 1 Mio. Token (Eingabe/Ausgabe), ab 01.12.2026 4,00 / 20,00 | ergänzen, Beschreibung „stärkstes Modell, nur mit Abrechnung“ |
| *(fehlt)* `gemini-3.8-flash` | Von Google für neue Projekte empfohlen; Freikontingent; 0,75 / 3,75, ab 01.01.2027 1,50 / 7,50 | ergänzen; Kandidat für die Vorgabe |
| `gemini-3.6-flash` | stabil, Freikontingent, gleicher Preis wie 3.8 | behalten |
| `gemini-3.5-flash` | steht in der Modellübersicht **nicht** | behalten, bis H1 (`GET /v1beta/models`) klärt, ob es das Modell noch gibt |
| `gemini-3.5-flash-lite` | stabil, Freikontingent, 0,30 / 2,50 | behalten |
| `gemini-3.1-flash-lite` | stabil, Freikontingent, 0,25 / 1,50 | behalten |
| `gemini-2.5-pro`, `-flash`, `-flash-lite` | „limited access“: nur für Konten, die sie früher genutzt haben | behalten, ans Ende der Liste, in `info.md` als „nur für Konten mit früherer Nutzung“ kennzeichnen — ein neuer Schlüssel bekommt dafür womöglich einen Fehler |

**Nur ergänzen, nicht entfernen.** Die Liste steht auch in `schema.model` von `config.yaml`. Fällt
dort ein Wert weg, den ein Nutzer gespeichert hat (z. B. `gemini-2.5-pro`), lehnt der
Supervisor die gespeicherten Optionen ab — das Add-on startet nicht, bis jemand die Auswahl von
Hand korrigiert. Ein Entfernen wäre ein Bruch und gehörte dann als solcher gekennzeichnet
(`!` im Commit, Hinweis im Changelog), samt Übergangsregel.

Mitzuändern, weil ein Test (`tests/unit/test_addon_config.py::test_model_list_matches_the_providers`)
sie gleichhält: die Auswahlliste `schema.model` in `skytech_omniai/config.yaml`. Ferner
`info.md` (Tabelle „Verfügbare Gemini-Modelle“), `docs/konfiguration.md` falls Modelle genannt
werden, und die Beispiele in den Provider-Tests. Die Oberfläche liest die Liste über
`/models`, dort ist nichts von Hand zu ändern.

Die Preise gehören nicht in den Code und nicht in die Auswahlbeschreibung — sie ändern sich
(zwei Erhöhungen sind schon angekündigt). Beschreibungen nennen die Eigenschaft („stärkstes
Modell, nur mit Abrechnung“), nicht den Betrag.

### 2.2 Werkzeuge: die API kann mehr, als das Add-on nutzt

Die Interactions-API kennt serverseitige Werkzeuge, die Google ausführt (nichts davon läuft im
Container):

| Werkzeug | Tool-Eintrag | Kosten | Auflagen |
|---|---|---|---|
| Seitenabruf | `{"type": "url_context"}` | kostenlos; abgerufener Inhalt zählt als Eingabetoken | Ruft laut Produktbeschreibung Adressen ab, die im Prompt stehen (Handprüfung H3) |
| Websuche | `{"type": "google_search"}` | **nicht im Freikontingent** (Gemini 3 und neuer); bezahlt 5.000 Suchanfragen im Monat frei, danach 14 US-Dollar je 1.000 | siehe unten |
| Code ausführen | `{"type": "code_execution"}` | — | läuft in Googles Umgebung; für OmniAI nicht benötigt |

**Auflagen der Websuche — hier liegt die eigentliche Hürde.** Die Gemini-API-Bedingungen
([Quelle](https://ai.google.dev/gemini-api/terms)) knüpfen „Grounding with Google Search“ an:

- Ergebnisse dürfen nur dem **Endnutzer angezeigt werden, der den Prompt gestellt hat**,
  zusammen mit den zugehörigen Suchvorschlägen („Search Suggestions“).
- Untersagt ist, Ergebnisse zu „cache, frame, syndicate, resell, analyze, train on, or otherwise
  learn from“.
- Nur in einer Anwendung, die „owned and operated by you“ ist.
- Google speichert Prompt, Kontext und Ausgabe dabei 30 Tage.

OmniAI gibt das JSON des Modells an Automationen zurück, die es **auswerten** (Home Assistant,
Skytech X). Die Suchvorschläge erreichen den Endnutzer dabei nicht, und die Antwort wird
maschinell weiterverarbeitet. Dass das den Bedingungen entspricht, lässt sich aus dem Text **nicht
sicher** ableiten; die Bedingungen sprechen von Anwendungen ohne Oberfläche nicht. Daraus folgt:

- **`web` darf bei Gemini nicht stillschweigend `google_search` einschalten.**
- Vorschlag: `web` ⇒ nur `url_context`; `google_search` erst nach ausdrücklicher Entscheidung des
  Users und mit eigenem Schalter (Entscheidung 2 in [README.md](README.md#entscheidungen-die-beim-user-liegen)).
- Ohne Websuche kann der Seitenabruf Fragen nicht beantworten, die keine Adresse enthalten
  („Wie wird das Wetter?“). Für solche Fälle bleiben `claude_sub` und `codex_sub` mit ihren
  eigenen Suchwerkzeugen.

Abbildung der Stufen:

| `tool_access` | `tools` im Rumpf | Anmerkung |
|---|---|---|
| `off` | *(keine)* | wie heute |
| `web` | `[{"type": "url_context"}]` | kostenlos; kein Container-Zugriff möglich |
| `full` | wie `web` | Befehle im Container gibt es bei der API nicht; Oberfläche und Doku weisen das aus |
| *(Variante)* `web` + Websuche | `[{"type": "google_search"}, {"type": "url_context"}]` | nur nach Entscheidung 2; nicht im Freikontingent |

Die Systemanweisung bekommt bei aktiven Werkzeugen, wie bei den CLIs, einen englischen Absatz,
dass Internetzugriff besteht und das Werkzeug benutzt werden soll — sonst liest das Modell „headless
endpoint“ als „kein Internet“ (Begründung in D-012).

**Ungeprüft:** Ob `response_format` (`application/json`, ohne Schema) mit Werkzeugen zusammen
angenommen wird. Die Doku zeigt die Kombination nur **mit** Schema
([Quelle](https://ai.google.dev/gemini-api/docs/structured-output)). Fällt die Kombination durch,
bleibt der Rückfall: bei aktiven Werkzeugen `response_format` weglassen und sich auf
`JSON_INSTRUCTION` plus `parse_json` verlassen — genau dafür gibt es die Auswertung. Handprüfung
H4 unten.

### 2.3 Strukturierte Ausgabe

`response_format` mit `schema` erzwingt gültiges JSON in der Form des Schemas und ist mit
Werkzeugen kombinierbar (Gemini 3, Vorschau). Für `/v1/completions` (D-020), wo der Aufrufer ein
Schema mitschickt, könnte der Provider es durchreichen, statt es nur als Text in den Prompt zu
schreiben. Die Prüfung mit `jsonschema` und der zweite Versuch bleiben auf jeden Fall bestehen:
Google ignoriert einige Schlüsselwörter (`minLength`, `maxLength`, `uniqueItems`, `contains`, …) und
lehnt sehr große Schemas mit einem 400 ab. **Optional**, nicht Teil des Mindestumfangs.

### 2.4 Nutzungsdaten

Die Antwort enthält `usage` mit `total_input_tokens`, `total_output_tokens`,
`total_thought_tokens`, `total_tokens` und `grounding_tool_count`. `/v1/completions` liefert heute
keine Nutzungsdaten ([../../roadmap.md](../../roadmap.md), M5). Weil die Fabrik je Anfrage eine
**neue** Provider-Instanz erzeugt (`ProviderFactory.create`), könnte `execute` den Wert in ein
Attribut der Instanz legen und `api_v1.py` ihn lesen — ohne die Signatur von `execute` zu ändern.
Das ist ein Eingriff in die gemeinsame Schnittstelle (D-005) und braucht einen eigenen Beschluss;
**optional**, siehe Plan.

## 3. Fehlermeldungen

Neue oder geänderte Sätze, alle ohne Technikjargon (Regel 12); die Originalantwort von Google
bleibt im Log. Welcher Code zu welchem Fall gehört, ist **zu belegen**, bevor die Zuordnung
gebaut wird (Aufzeichnung echter Antworten mit eigenem Schlüssel, danach als feste Testdaten):

| Fall | Entwurf der Meldung |
|---|---|
| Modell nur mit Abrechnung (z. B. `gemini-4-argon` im Freikontingent) | „Dieses Gemini-Modell ist nur mit aktivierter Abrechnung bei Google nutzbar. Bitte ein anderes Modell wählen oder die Abrechnung aktivieren.“ |
| Websuche nicht erlaubt (Freikontingent) | „Die Websuche von Gemini braucht ein Google-Konto mit Abrechnung. Im Add-on die Werkzeuge auf „web“ oder „off“ stellen oder die Abrechnung aktivieren.“ |
| Freikontingent des Tages erschöpft | bestehender Satz zu 429, ergänzt um den Hinweis auf die Abrechnung |
| Modell unbekannt (z. B. ein `gemini-2.5-*` für ein neues Konto) | bestehender Satz zu 404 |

## 4. Kosten und Vorteile aus dem Abo

| Weg | Wirkung | Voraussetzung |
|---|---|---|
| **Freikontingent** | `gemini-3.8-flash`, `3.6-flash`, `3.5-flash-lite`, `3.1-flash-lite` kostenlos, mit Limits je Projekt (aktuelle Werte im [AI Studio](https://aistudio.google.com/rate-limit)) | Schlüssel aus AI Studio. Kein Websuche-Werkzeug, kein `gemini-4-argon` |
| **Abrechnung (Stufe 1)** | Höhere Limits, Websuche möglich, `gemini-4-argon`; Obergrenze der Stufe 1 laut Limits-Seite 250 US-Dollar, in 10 Minuten höchstens 10 US-Dollar | Rechnungskonto verknüpfen; es kann auch ein Vorab-Guthaben verlangt werden ([Limits](https://ai.google.dev/gemini-api/docs/rate-limits)) |
| **Cloud-Guthaben aus AI Pro** | 10 US-Dollar im Monat (Developer Program Premium, in AI Pro enthalten) | einmalig im Developer-Programm unter „Benefits“ aktivieren und an ein Rechnungskonto binden (Berichte). **Ob es direkte Gemini-API-Aufrufe deckt, ist von Google widersprüchlich dargestellt** — in der Cloud-Konsole unter „Billing → Credits“ in der Spalte „Applicable to“ prüfen, bevor man darauf baut |
| **Abo-Nutzungsfenster von AI Pro** | gilt **nicht** für API-Aufrufe | — |

Rechenbeispiel zur Einordnung (Annahme: 2.000 Eingabe- und 500 Ausgabetoken je Anfrage, Modell
`gemini-3.8-flash`; Denktoken zählen als Ausgabe und können mehr kosten): etwa 0,0034 US-Dollar je
Anfrage, also rund 3.000 Anfragen für 10 US-Dollar. Ab dem 01.01.2027 verdoppelt sich der Preis
dieses Modells laut Preisseite; dann sind es rund 1.500.

## Datenschutz

| Punkt | Befund |
|---|---|
| Freikontingent | „Unpaid Services“: Google nutzt Eingaben und Ausgaben zur Verbesserung seiner Produkte, Menschen können mitlesen. **Keine Smart-Home-Daten senden.** |
| Mit Abrechnung | „Paid Services“: keine Nutzung für Produktverbesserung; Protokollierung nur kurz zur Missbrauchserkennung |
| **EWR, Schweiz, Vereinigtes Königreich** | Die Regeln der „Paid Services“ zur Datennutzung gelten laut Bedingungen für **alle** Dienste dort, auch das Freikontingent. Zugleich verlangen die Bedingungen für API-Clients, die Nutzern dort bereitgestellt werden, bezahlte Dienste. Für einen privaten Eigenbetrieb ist die Auslegung nicht eindeutig; die sichere Seite ist die aktivierte Abrechnung |
| `store: false` | bleibt gesetzt: kein Verlauf bei Google (D-007) |
| Websuche | Google speichert Prompt, Kontext und Ausgabe dennoch 30 Tage |
| Seitenabruf | Abgerufene Adressen und Inhalte gehen an Google |

Nachzuziehen in [../../sicherheit-datenschutz.md](../../sicherheit-datenschutz.md): Tabelle
„Externe Dienste“ (Google: zusätzlich abgerufene Adressen bei `web`) und der Satz zum
Freikontingent.

## 5. Handprüfungen mit eigenem Schlüssel

Die Tests laufen ohne Netz und ohne Schlüssel ([../../test-strategie.md](../../test-strategie.md)).
Folgendes lässt sich nur mit einem echten Schlüssel belegen und gehört in die Abnahme:

| Nr. | Prüfung | Erwartung |
|---|---|---|
| H1 | `GET https://generativelanguage.googleapis.com/v1beta/models` mit dem Schlüssel | enthält die Modelle der neuen Liste; Antwort zu `gemini-3.5-flash` und den `2.5`-Modellen festhalten |
| H2 | Je neues Modell eine einfache Anfrage über `/ask` | gültiges JSON zurück |
| H3 | `web` mit einer Adresse im Prompt | Inhalt der Seite fließt in die Antwort ein; Antwort wird gelesen (`model_output`) |
| H4 | Kombination `response_format` ohne Schema mit `tools` | angenommen — oder dokumentierter Rückfall (Abschnitt 2.2) |
| H5 | Freikontingent-Schlüssel mit `gemini-4-argon` und mit `google_search` | Antwortcodes und Texte für Abschnitt 3 festhalten, als Testdaten ablegen |
| H6 | Antwort enthält `usage` mit den genannten Feldern | Namen stimmen (Voraussetzung für 2.4) |
