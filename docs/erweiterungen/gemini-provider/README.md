# Erweiterung: Gemini-Provider mit Google-AI-Pro-Abo

> **Stand 28.10.2026: Der Abo-Weg ist umgesetzt** (Anbieter `gemini_sub`, Entscheidung
> [D-022](../../adr/D-022-gemini-abo-antigravity.md)); die **Handprüfung mit einem echten Konto
> steht aus**. Der Ausbau des Schlüssel-Wegs (`gemini`) ist **nicht** umgesetzt und hier nur geplant.
> Was das Add-on heute tut, steht in [../../architektur.md](../../architektur.md); Abweichungen davon
> in [../../bekannte-luecken.md](../../bekannte-luecken.md).

## Auftrag

Die Gemini-Modelle über das **Google-AI-Pro-Abo** nutzen — wie bei `claude_sub` und `codex_sub`
über das Abo statt über einen nach Verbrauch abgerechneten Schlüssel — und das so, dass es in die
bestehende Provider-Struktur passt (D-005).

## Ergebnis der Recherche (27.10.2026)

1. **Der naheliegende Weg ist weg.** Die Gemini CLI bedient Google-AI-Pro-Konten seit dem
   18.06.2026 nicht mehr. Nachfolger für Abo-Nutzer ist die **Antigravity CLI** (`agy`).
2. **Technisch geht es.** `agy -p --output-format json` ist ein Headless-Modus wie `claude -p`, mit
   einem Binary für Alpine/musl, das auf dem Basisimage des Add-ons läuft. Das Problem ist die
   **Anmeldung**: kein Anmeldebefehl, kein Token zum Einfügen — gelöst durch eine Anmeldung im
   Add-on selbst, siehe D-022.
3. **Google schließt genau diesen Einsatz für Privatabos aus.** Die FAQ der Antigravity CLI: `agy`
   in Anwendungen einzupacken wird **unter Verbraucherplänen nicht unterstützt** (Wortlaut und
   Quelle in [recherche.md](recherche.md#die-entscheidende-klausel)). Die Bedingungen nennen als
   Folge die Sperrung des Kontos. OmniAI ist so eine Anwendung.
4. **Der von Google für Fremdanwendungen vorgesehene Weg ist der API-Schlüssel.** Den hat das
   Add-on (`gemini`, D-007). Das Abo selbst lässt sich darüber nicht anzapfen; AI Pro bringt dort nur
   ein Cloud-Guthaben und das Freikontingent der Flash-Modelle.
5. **Der Schlüssel-Provider ist veraltet und hat keine Werkzeuge** (Modellliste ohne `gemini-4-argon`
   und `gemini-3.8-flash`, `tool_access` ohne Wirkung) — Plan in [api-weg.md](api-weg.md).

Die Recherche empfahl, den Abo-Weg zurückzustellen. Der User hat am 27.10.2026 in Kenntnis des
Risikos anders entschieden; das steht so im ADR und wird nicht verschwiegen.

## Was daraus wurde

| Spur | Stand | Wo |
|---|---|---|
| **Abo-Weg über `agy`** (`gemini_sub`) | **umgesetzt**, Handprüfung H1 bis H10 offen | Code: `skytech_omniai/providers/gemini_sub_*.py`; Entscheidung, Messungen und Handprüfung: [D-022](../../adr/D-022-gemini-abo-antigravity.md); Befunde zur CLI: [abo-weg-antigravity.md](abo-weg-antigravity.md) |
| **API-Weg ausbauen** (`gemini`) | **offen**, nur geplant | [api-weg.md](api-weg.md), Arbeitspakete in [umsetzungsplan.md](umsetzungsplan.md) |

## Entscheidungen, die beim User liegen (Schlüssel-Weg)

1. **Websuche (`google_search`) bei Gemini zulassen?** Sie funktioniert nur mit Abrechnung, kostet
   nach 5.000 Suchanfragen im Monat 14 US-Dollar je 1.000 und ist laut Googles Bedingungen daran
   gebunden, dass die Ergebnisse samt Suchvorschlägen dem fragenden Endnutzer angezeigt und nicht
   ausgewertet werden. Eine Brücke, deren JSON Automationen weiterverarbeiten, erfüllt das nicht
   erkennbar. Vorschlag: `web` bedeutet bei Gemini nur Seitenabruf (`url_context`).
2. **Standardmodell:** Alias `gemini-flash-latest` behalten (zeigt auf das jeweils neueste
   Flash-Modell, verändert sich ohne Zutun) oder auf `gemini-3.8-flash` festnageln.

## Nicht geprüft

- Ob die Bedingungen von Anthropic und OpenAI für den bestehenden Betrieb von `claude_sub` und
  `codex_sub` ähnliche Klauseln enthalten.
- Das Verhalten von `agy` **nach** einer echten Anmeldung — das ist die Handprüfung in D-022.

## Dateien

| Datei | Inhalt |
|---|---|
| [recherche.md](recherche.md) | Befunde mit Quellen, Vergleich aller Wege, Googles Wortlaut |
| [abo-weg-antigravity.md](abo-weg-antigravity.md) | Steckbrief der `agy`-CLI, Messungen, Risiken des umgesetzten Wegs |
| [api-weg.md](api-weg.md) | Plan: Ausbau des Providers `gemini` (Schlüssel, Modelle, Werkzeuge, Kosten, Datenschutz) |
| [umsetzungsplan.md](umsetzungsplan.md) | Arbeitspakete für den Schlüssel-Weg |
