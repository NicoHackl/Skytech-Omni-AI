# Recherche: Gemini mit dem Google-AI-Pro-Abo

Stand: 27.10.2026. Alle Quellen an diesem Tag abgerufen. Google ändert Bedingungen und Produkte
in diesem Bereich seit Monaten laufend — vor einer Umsetzung die markierten Stellen erneut prüfen.

Kennzeichnung der Belastbarkeit:

| Marke | Bedeutung |
|---|---|
| **geprüft** | Am 27.10.2026 selbst ausgeführt (Container mit dem Basisimage des Add-ons) |
| **Google** | Steht in Googles eigener Doku, FAQ, Bedingungen oder Ankündigung |
| **Bericht** | Meldung von Nutzern oder Dritten (Issues, Foren, Blogs); nicht bestätigt |

## 1. Die Gemini CLI ist für Abo-Nutzer abgeschaltet

| Befund | Marke | Quelle |
|---|---|---|
| Ab dem 18.06.2026 bedient die Gemini CLI Anfragen von Google AI Pro, Google AI Ultra und kostenlosen Code-Assist-Konten **nicht mehr**. Nachfolger: Antigravity CLI | Google | [Ankündigung im Developers Blog](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) |
| Unverändert bleiben Code Assist Standard/Enterprise (Unternehmen) und bezahlte API-Schlüssel | Google | dieselbe Ankündigung |
| Banner „Gemini CLI was replaced by Antigravity CLI on June 18th, 2026“ auf den Doku-Seiten der Gemini CLI | Google | [Kontingent und Preise](https://geminicli.com/docs/resources/quota-and-pricing/) |
| Die Kontingenttabelle dort (AI Pro: 1.500 Anfragen am Tag) ist damit **überholt**; Authentifizierungsguide und Preisseite widersprechen der Ankündigung noch | Google / Bericht | [Issue gemini-cli #29796](https://github.com/google-gemini/gemini-cli/issues/29796) |

Folge: Jede ältere Anleitung „`gemini -p` mit Google-Login im Headless-Betrieb“ (auch das, was
sich zu D-013 spiegelbildlich anbieten würde) ist für ein AI-Pro-Konto **tot**.

## 2. Der Nachfolger: Antigravity CLI (`agy`)

Technischer Steckbrief mit Messungen: [abo-weg-antigravity.md](abo-weg-antigravity.md). Hier nur
das, was für die Entscheidung zählt.

| Befund | Marke | Quelle |
|---|---|---|
| Einziger Installationsweg: `curl -fsSL https://antigravity.google/cli/install.sh \| bash`; Binary heißt `agy` | Google | [Repo](https://github.com/google-antigravity/antigravity-cli), [Einstieg](https://antigravity.google/docs/getting-started) |
| Das Skript erkennt musl (Alpine) und lädt `linux_<arch>_musl`; Version 1.4.8 für amd64 und arm64 | geprüft | Skript und Manifeste, siehe Steckbrief |
| Headless: `agy -p "…" --output-format json` mit `--json-schema`, `--model`, `--print-timeout` | Google | [Headless-Doku](https://antigravity.google/docs/cli/headless/) |
| Anmeldearten: Persönliches Google-Konto (Free/Pro/Ultra), Unternehmens-/Cloud-Anmeldung, API-Schlüssel, Application Default Credentials | Google | [Anmeldung](https://antigravity.google/docs/install?tab=cli) |
| Persönliche Anmeldung liegt im **Schlüsselbund des Betriebssystems**; ein Dateispeicher ist in der Doku nicht beschrieben | Google | dieselbe Seite |
| Headless nutzt „zwischengespeicherte Anmeldedaten“ einer früheren interaktiven Anmeldung; für CI empfiehlt Google den API-Schlüssel | Google | Headless-Doku, Anmeldung |
| Kontingent bei AI Pro: 5-Stunden-Fenster bis zum Wochenlimit, Verbrauch richtet sich nach der Arbeit des Agenten, keine Zahlen | Google | [Pläne](https://antigravity.google/docs/plans) |
| Verfügbar in Deutschland und Österreich; nur für Konten ab 18 Jahren und nur private Google-Konten | Google | [FAQ](https://www.antigravity.google/docs/faq) |

## Die entscheidende Klausel

Das ist der Befund, der den Abo-Weg ausbremst. Wortlaut aus der offiziellen FAQ der Antigravity
CLI ([antigravity.google/docs/faq](https://www.antigravity.google/docs/faq)), Frage und Antwort
unverändert:

> **Can I use Antigravity CLI headless mode in third-party coding agents or automate account
> switching?**
> Antigravity CLI headless mode (`agy -p`) is intended for direct scripting and CI workflows.
> Wrapping `agy` inside third-party coding agents or applications, or automating account
> rotation, is not supported under consumer plans.

Dazu zwei weitere Stellen:

> **Why can't I use third-party software (such as Claude Code, OpenClaw, or OpenCode) with my
> Antigravity login?**
> Using third-party software, tools, or services to access Antigravity is a violation of our
> Terms of Service and severely degrades the experience for legitimate product users. Such
> actions can result in suspension or termination of your account. To use a third-party coding
> agent with Gemini, we recommend using a Gemini Enterprise or Google AI Studio API key.

Nutzungsbedingungen ([antigravity.google/terms](https://antigravity.google/terms)), Klausel 6
(gekürzt): Als untersagt gilt „Using third party software, tools, or services to access the
Service“, ausdrücklich mit dem Beispiel „using OpenClaw with Antigravity OAuth“ und dem Zusatz
„This includes, but is not limited to, using the Service in connection with products not provided
by us“. Folge: „may be grounds for suspension or termination of your Antigravity and/or Gemini
CLI accounts“. Klausel 4 macht den Nutzer zudem allein verantwortlich für alles, was ein
KI-Agent in seinem Namen tut.

**Einordnung für OmniAI:**

- OmniAI nimmt Anfragen über HTTP an und gibt sie an `agy` weiter, für Home Assistant und für
  Skytech X. Das ist „`agy` inside applications“ — nicht „direktes Scripting“.
- Google Pro/Ultra sind **Verbraucherpläne**; die Ausnahme „Gemini Enterprise oder Workspace
  unter den Bedingungen des Administrators“ gilt für sie nicht.
- Belegt sind Sperrungen für das **Mitnehmen des OAuth-Zugangs in Fremdwerkzeuge** (OpenClaw,
  Antigravity-Server für Nicht-Antigravity-Produkte), z. B. im
  [Forum](https://discuss.ai.google.dev/t/account-restricted-without-warning-google-ai-ultra-oauth-via-openclaw/122778)
  und in [gemini-cli Diskussion #20632](https://github.com/google-gemini/gemini-cli/discussions/20632).
  Einen belegten Fall für einen reinen `agy -p`-Aufruf aus einem eigenen Dienst habe ich **nicht**
  gefunden. „Nicht belegt“ heißt aber nicht „erlaubt“: Googles Text nennt den Einsatz
  ausdrücklich nicht unterstützt.
- Nicht auszuschließen, dass Google das später lockert. Das ist die Wiederaufnahmebedingung in
  [adr-entwurf.md](adr-entwurf.md).

Gleiche Lage bei der alten Gemini CLI: Die
[FAQ](https://geminicli.com/docs/resources/faq/) nennt „Using third-party software, tools, or
services to harvest or piggyback on Gemini CLI's OAuth authentication“ einen direkten Verstoß
gegen die Bedingungen und empfiehlt für Fremd-Agenten einen Vertex- oder AI-Studio-Schlüssel.

## 3. Was das Abo über die API hergibt

| Befund | Marke | Quelle |
|---|---|---|
| Vorteile von AI Pro/Ultra für Entwickler gelten **nur in der Weboberfläche von AI Studio**; „Direct API use is billed separately“ | Google | [Google AI plans](https://ai.google.dev/gemini-api/docs/google-ai-plans) |
| Agenten in AI Studio (Deep Research, Antigravity Preview) sind in den Plänen **nicht** enthalten | Google | dieselbe Seite |
| Google-Developer-Program Premium ist in AI Pro enthalten: „$10 GenAI and Cloud monthly credit“ (Ultra 20 TB: 40, Ultra 30 TB: 100 US-Dollar) | Google | [Plans and pricing](https://developers.google.com/program/plans-and-pricing) |
| Aktivierung nicht auf der Seite beschrieben; Berichte: einmalig im Developer-Programm unter „Benefits“ das Guthaben an ein Cloud-Rechnungskonto binden | Bericht | [Blog](https://medium.com/google-cloud/from-prototype-to-production-how-google-ai-subscription-bridges-the-last-mile-for-ai-developers-dd80bb149a3e) |
| Ob das Guthaben **direkte Gemini-API-Aufrufe** deckt, ist uneindeutig: die Plans-Seite sagt „any Google product“, die Google-AI-plans-Seite nur AI Studio | Google (widersprüchlich) | beide Seiten |
| Mit Schlüssel und Abrechnung: Datenverarbeitung nach den Bedingungen für „Paid Services“ | Google | [Gemini API Terms](https://ai.google.dev/gemini-api/terms) |

Daraus folgt: Das Abo **selbst** (die Nutzungsfenster von AI Pro) ist über die API nicht
erreichbar. Ein echter Vorteil ist das Cloud-Guthaben, sofern es auf die Gemini API anrechenbar
ist (vor Aktivierung unter „Billing → Credits → Applicable to“ prüfen), und das Freikontingent
der Flash-Modelle.

## 4. Zustand der Gemini API (Stand 27.10.2026)

| Befund | Marke | Quelle |
|---|---|---|
| Aktuelle Modelle: `gemini-4-argon` (Flaggschiff, stabil), `gemini-3.8-flash` (empfohlen für neue Projekte, stabil), `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` | Google | [Modelle](https://ai.google.dev/gemini-api/docs/models) |
| `gemini-2.5-*`: „limited access“, nur für Konten, die sie früher genutzt haben; nicht abgekündigt | Google | dieselbe Seite |
| `gemini-3.5-flash` fehlt in der Modellübersicht (nur `3.5-flash-lite` steht dort); im Code noch geführt. Vor dem Entfernen gegen die Modellliste der API prüfen (`GET /v1beta/models`) | Google | dieselbe Seite |
| Preise je 1 Mio. Token: `gemini-3.8-flash` 0,75 / 3,75 US-Dollar (ab 01.01.2027 1,50 / 7,50), `gemini-4-argon` 2,00 / 10,00 (ab 01.12.2026 4,00 / 20,00), `gemini-3.5-flash-lite` 0,30 / 2,50, `gemini-3.1-flash-lite` 0,25 / 1,50 | Google | [Preise](https://ai.google.dev/gemini-api/docs/pricing) |
| Freikontingent: `gemini-3.8-flash`, `3.6-flash`, `3.5-flash-lite`, `3.1-flash-lite` kostenlos nutzbar; `gemini-4-argon` **nicht** | Google | dieselbe Seite |
| Websuche (`google_search`) bei Gemini 3 und neuer: nicht im Freikontingent; bezahlt 5.000 Suchanfragen im Monat frei, danach 14 US-Dollar je 1.000 | Google | Preise, [Google Search](https://ai.google.dev/gemini-api/docs/google-search) |
| Seitenabruf (`url_context`) kostenlos; die abgerufenen Seiten zählen als Eingabetoken | Google | Preise |
| Strukturierte Ausgabe mit `response_format.schema` lässt sich bei Gemini 3 mit `google_search` und `url_context` kombinieren (Vorschau) | Google | [Strukturierte Ausgabe](https://ai.google.dev/gemini-api/docs/structured-output) |
| Interactions-Antwort: `usage` mit `total_input_tokens`, `total_output_tokens`, `total_thought_tokens`, `total_tokens`, `grounding_tool_count` | Google | [Interactions-Referenz](https://ai.google.dev/api/interactions-api) |
| Gemini API Terms: Freikontingent = „Unpaid Services“ (Inhalte dienen der Produktverbesserung, Menschen können mitlesen); im **EWR, in der Schweiz und im Vereinigten Königreich** gelten die Regeln der „Paid Services“ für alle Dienste. Grounding mit Google Search speichert Eingabe und Ausgabe 30 Tage | Google | [Bedingungen](https://ai.google.dev/gemini-api/terms) |

Das bildet den Rahmen für [api-weg.md](api-weg.md).

## 5. Vergleich aller Wege

| Weg | Nutzt Abo-Kontingent | Von Google für Fremdanwendungen vorgesehen | Im Add-on machbar | Urteil |
|---|---|---|---|---|
| **A — Gemini API mit AI-Studio-Schlüssel** (`gemini`, vorhanden) | nein (Verbrauch; Freikontingent; evtl. Cloud-Guthaben aus AI Pro) | **ja**, von Google ausdrücklich empfohlen | ja, schon gebaut | **Umsetzen/ausbauen** |
| **B — `agy -p` mit Google-AI-Pro-Login** | ja (5-Stunden-Fenster, Wochenlimit) | **nein**, FAQ: in Anwendungen nicht unterstützt | technisch möglich, Anmeldung im Container ungeklärt | **Zurückstellen** |
| C — Gemini CLI mit Google-Login | — | — | seit 18.06.2026 für AI Pro abgeschaltet | nicht möglich |
| D — `gemini`/`agy` mit API-Schlüssel statt A | nein | ja | ja, aber 196 MB bzw. Node-Abhängigkeit mehr im Bild | verworfen: A liefert Websuche über die API selbst, die CLI bringt nichts hinzu |
| E — Abo-Token direkt gegen die Cloud-Code-Schnittstelle (Weg der OpenClaw-/opencode-Plugins) | ja | **nein, ausdrücklich verboten** (Klausel 6 nennt es) | ja, aber Verstoß und Sperrrisiko | verworfen |
| F — Gemini Enterprise / Workspace / Cloud-Projekt (`oauth-business`, ADC, Vertex) | Unternehmenslizenz, nicht AI Pro | ja, es gelten die Bedingungen des Administrators | machbar, anderer Zugangstyp | nur bei Bedarf, kein Abo des Users |

## Quellenverzeichnis

Google, Antigravity: [Ankündigung](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) ·
[FAQ](https://www.antigravity.google/docs/faq) ·
[Nutzungsbedingungen](https://antigravity.google/terms) ·
[Einstieg](https://antigravity.google/docs/getting-started) ·
[Headless](https://antigravity.google/docs/cli/headless/) ·
[Referenz](https://antigravity.google/docs/cli/reference/) ·
[Anmeldung](https://antigravity.google/docs/install?tab=cli) ·
[Berechtigungen](https://antigravity.google/docs/permissions?tab=cli) ·
[Pläne](https://antigravity.google/docs/plans) ·
[Fehlersuche](https://antigravity.google/docs/cli/troubleshooting) ·
[Regeln](https://antigravity.google/docs/rules) ·
[Änderungsliste](https://raw.githubusercontent.com/google-antigravity/antigravity-cli/main/CHANGELOG.md)

Google, Gemini API: [Modelle](https://ai.google.dev/gemini-api/docs/models) ·
[Preise](https://ai.google.dev/gemini-api/docs/pricing) ·
[Limits](https://ai.google.dev/gemini-api/docs/rate-limits) ·
[Bedingungen](https://ai.google.dev/gemini-api/terms) ·
[Google AI plans](https://ai.google.dev/gemini-api/docs/google-ai-plans) ·
[Interactions](https://ai.google.dev/gemini-api/docs/interactions) ·
[Interactions-Referenz](https://ai.google.dev/api/interactions-api) ·
[Google Search](https://ai.google.dev/gemini-api/docs/google-search) ·
[Strukturierte Ausgabe](https://ai.google.dev/gemini-api/docs/structured-output) ·
[Developer Program](https://developers.google.com/program/plans-and-pricing)

Gemini CLI: [Repo](https://github.com/google-gemini/gemini-cli) ·
[FAQ](https://geminicli.com/docs/resources/faq/) ·
[Kontingent](https://geminicli.com/docs/resources/quota-and-pricing/)

Issues zum Anmelden und Headless-Betrieb (Berichte, Stand der Seiten am 27.10.2026):
[#479 Dateispeicher im Container](https://github.com/google-antigravity/antigravity-cli/issues/479) ·
[#223 Headless-Anmeldung](https://github.com/google-antigravity/antigravity-cli/issues/223) ·
[#76 Ausgabe ohne Terminal](https://github.com/google-antigravity/antigravity-cli/issues/76) ·
[#950 Eignungsprüfung auf Servern](https://github.com/google-antigravity/antigravity-cli/issues/950) ·
[#1336 Wahl Schlüsselbund/Datei](https://github.com/google-antigravity/antigravity-cli/issues/1336)
