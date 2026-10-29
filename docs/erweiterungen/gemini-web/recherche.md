# Recherche: Das Limit der Gemini-Web-App ansprechen

Stand: 29.10.2026. Alle Quellen an diesem Tag abgerufen. Google ändert Produkte und Bedingungen in
diesem Bereich laufend — vor der Umsetzung die markierten Stellen erneut prüfen. Die Recherche zu
`agy` und zur API steht in [../gemini-provider/recherche.md](../gemini-provider/recherche.md) und
wird hier nicht wiederholt.

Kennzeichnung der Belastbarkeit:

| Marke | Bedeutung |
|---|---|
| **Google** | Steht in Googles eigener Doku, Hilfe oder Bedingungen; am 29.10.2026 selbst gelesen |
| **Projekt** | Steht im Repo oder auf PyPI des Projekts `gemini-webapi`; am 29.10.2026 gelesen, nicht ausgeführt |
| **Bericht** | Meldung von Nutzern oder Dritten (Foren, Blogs); nicht bestätigt |
| **offen** | Nicht geprüft — Prüfauftrag für den Spike ([umsetzungsplan.md](umsetzungsplan.md#ap-2--spike)) |

## 1. Das Limit der Web-App

| Befund | Marke | Quelle |
|---|---|---|
| Das Limit der Gemini-Apps ist rechenzeitbasiert: Es erneuert sich alle fünf Stunden, bis das Wochenlimit erreicht ist. AI Pro hat das Vierfache des Standardlimits. Zahlen je Tag nennt Google nicht | Google | [Limits der Gemini-Apps](https://support.google.com/gemini/answer/16275805) |
| Deep Research hat „High“ als relative Nutzungskosten und verbraucht mehr vom Limit als ein einfacher Chat | Google | dieselbe Seite |
| Ob das Limit nur für die Web-App gilt oder auch für andere Zugänge, sagt die Seite nicht | Google (Lücke) | dieselbe Seite |
| Die Gemini-API wird getrennt abgerechnet; die Vorteile von AI Pro gelten für Entwickler nur in der Weboberfläche von AI Studio | Google | [Google AI plans](https://ai.google.dev/gemini-api/docs/google-ai-plans) |
| Die „Google One AI credits“ sind ein eigenes System und in AI Studio nicht nutzbar | Google | dieselbe Seite |
| `agy` hat einen eigenen Pool: Antigravity meldet „Limit erreicht“, während die Gemini-App noch Raum zeigt. Googles Erhöhung vom Mai 2026 galt nur in Antigravity | Bericht | [Forum](https://discuss.ai.google.dev/t/antigravitys-usage-quota-is-very-restrictive/146716), [Android Authority](https://androidauthority.com/gemini-antigravity-limits-increased-3670209) |

Folge: Ein offizieller Weg zum Limit der Web-App besteht nicht. Es bleibt, die Web-App selbst
anzusprechen, so wie es der Browser tut.

## 2. Die Bibliothek `gemini-webapi`

| Befund | Marke | Quelle |
|---|---|---|
| Ein inoffizieller, asynchroner Python-Client für die Gemini-Web-App, „reverse-engineered“. Keine erkennbare Verbindung zu Google | Projekt | [Repo](https://github.com/HanaokaYuzu/Gemini-API) |
| Aktuelle Version 2.1.1, Lizenz **AGPL-3.0**, verlangt Python **3.11 oder neuer** | Projekt | [PyPI](https://pypi.org/project/gemini-webapi/) |
| Abhängigkeiten: `curl-cffi ~=0.16.2`, `loguru ~=0.7.3`, `orjson ~=3.11.9`, `pydantic ~=2.12.5`; optional `browser-cookie3` | Projekt | PyPI |
| Die drei übersetzten Pakete (`curl-cffi`, `orjson`, `pydantic-core` unter `pydantic`) brauchen Wheels für **musl (Alpine) auf aarch64 und amd64** und für **Python 3.11 und 3.14** (CI-Matrix) | offen | — |
| Anmeldung: Die Cookies `__Secure-1PSID` und `__Secure-1PSIDTS` aus einem angemeldeten Browser; ein Weg über Benutzername und Kennwort besteht nicht | Projekt | Repo |
| Der Client erneuert `__Secure-1PSIDTS` im Hintergrund, solange der Prozess läuft, und legt die erneuerten Cookies ab (Pfad über `GEMINI_COOKIE_PATH`). **Ob sich der Pfad je Konto statt über eine Umgebungsvariable setzen lässt, ist offen** | Projekt / offen | Repo |
| Hinweis des Projekts: Cookies in einer eigenen, kurzlebigen Browsersitzung (privates Fenster) holen; Chromium-Browser mit Device Bound Session Credentials halten Cookies unter Umständen nur wenige Stunden | Projekt | Repo |
| Das Projekt rät für Dauerbetrieb zu einem eigenen Konto, weil `__Secure-1PSIDTS` bei Nutzung desselben Kontos andernorts oft ungültig wird | Projekt | [PyPI 0.3.1](https://pypi.org/project/gemini-webapi/0.3.1) |
| Funktionen: Modelle werden beim Start **aus dem Konto** gelesen (Namen wie `gemini-pro`, `gemini-flash`), Dateien und Bilder als Anhang, Gems, Bild-, Video- und Audioerzeugung, Deep Research, Erweiterungen, Streaming, **temporäre Chats**, Lesen und Löschen des Verlaufs | Projekt | Repo |
| Rate Limits nennt das Projekt nicht | Projekt | Repo |
| Ausführung außerhalb eines Browsers: Anmeldeprüfungen von Google (Captcha, Bestätigung) auf einer Serveradresse sind möglich | offen | — |

### Fehlerarten der Bibliothek

Die Bibliothek unterscheidet die Fälle, die der Wechsel der Konten braucht, **als eigene Klassen**.
Bei `agy` hing das an einem Textmuster der CLI (`QUOTA_MARKER`, bekannte Lücke); hier nicht.

| Klasse | Bedeutung laut Quelltext | Reaktion des Anbieters |
|---|---|---|
| `UsageLimitExceededError` | Nutzungslimit des Modells erreicht | Konto in Wartezeit, nächstes Konto |
| `AuthError` | Anmeldung oder Cookies ungültig | Konto auf „Anmeldung abgelaufen“, nächstes Konto |
| `TemporarilyBlockedError` | HTTP 429, die **Adresse** ist vorübergehend gesperrt | **kein** Wechsel (trifft jedes Konto gleich); Anbieter pausiert, Meldung mit Wartezeit |
| `ModelInvalidError` | Modellkennung ungültig | Rückmeldung an den Aufrufer, kein Wechsel |
| `TimeoutError` | Zeitüberschreitung | `ProviderTimeout`, kein Wechsel |
| `GeminiError` (Oberklasse), `APIError` | Nicht behandelter Fehler von Google, bzw. Fehler im Paket | allgemeine Meldung, Ursache ins Log, kein Wechsel |

Quelle: [`exceptions.py`](https://github.com/HanaokaYuzu/Gemini-API/blob/master/src/gemini_webapi/exceptions.py),
Marke **Projekt**. Ob `UsageLimitExceededError` einen Zeitpunkt für die Erneuerung mitliefert, ist
**offen**.

## 3. Bedingungen und Risiko

| Befund | Marke | Quelle |
|---|---|---|
| Googles Nutzungsbedingungen untersagen „reverse engineering our services“, das Umgehen von Schutzmaßnahmen und das automatisierte Auslesen von Inhalten gegen maschinenlesbare Vorgaben | Google | [Bedingungen](https://policies.google.com/terms) |
| Google darf den Zugang sperren oder das Konto löschen, wenn jemand die Bedingungen „materially or repeatedly“ verletzt oder durch Verhalten Schaden anrichtet; bei Irrtum gibt es einen Einspruch | Google | dieselbe Seite |
| **Belegte Sperrungen** betreffen das Mitnehmen des Produkt-Logins in Fremdwerkzeuge (OpenClaw, Antigravity-Proxys) | Bericht | [Diskussion](https://github.com/google-gemini/gemini-cli/discussions/20632) |
| Für **cookie-basierte Clients der Web-App** fand die Recherche **keinen belegten Sperrfall**. „Nicht belegt“ heißt nicht „erlaubt“ | Bericht (Lücke) | Websuche 29.10.2026 |
| Einsprüche gegen Sperrungen bleiben laut Berichten oft ohne Antwort | Bericht | Foren |

**Einordnung:** Das Risiko gleicht dem von `gemini_sub` (D-022, D-024) und kann mit jedem weiteren
Konto steigen. Das eigene Konto begrenzt den Schaden auf dieses Konto samt seinem Abo, **sofern es
wirklich getrennt ist**: kein gemeinsames Zahlungsprofil, keine Wiederherstellungsadresse, die auf das
Hauptkonto zeigt, keine Daten darin.

## Nicht geprüft

- Ob die Bibliothek auf `ghcr.io/home-assistant/*-base:3.19` (Alpine, musl) mit den drei übersetzten
  Paketen installiert und läuft; ob es für Python 3.14 Wheels gibt.
- Wie lange die Cookies eines Kontos auf einer Serveradresse halten, und ob Google dort zusätzliche
  Anmeldeprüfungen verlangt.
- Welche Modellnamen ein AI-Pro-Konto in der Web-App tatsächlich anbietet und wie sie sich zu den
  Namen der API verhalten.
- Ob `UsageLimitExceededError` bei erreichtem **Wochenlimit** genauso auftritt wie beim 5-Stunden-Fenster.
- Ob temporäre Chats, Anhänge und mehrere gleichzeitige Anfragen je Konto zuverlässig laufen.
- Wann Version 2.1.1 erschien und wie oft das Projekt Änderungen von Google nachzieht (Pflegezustand).

Alle Punkte sind Prüfaufträge im [Spike](umsetzungsplan.md#ap-2--spike), keine Annahmen.
