# Vertrag Skytech X ↔ Skytech OmniAI

| | |
|---|---|
| Anbieter | Skytech OmniAI (dieses Repo) — setzt `/v1/…` um |
| Nutzer | Skytech X Backend (`Skytech-X-Backend`); Weboberfläche und iOS-App sprechen nur mit dem Backend |
| Schnittstelle | HTTP, Token-Pflicht, versioniert unter `/v1/…` |
| Version | 1.2.1 (siehe `info.version` in der OpenAPI-Datei) |
| Maschinenlesbarer Vertrag | [omniai-api-v1.yaml](omniai-api-v1.yaml) |
| Master | `Skytech-X-Backend/contract/contract_skytech_x_omniai/omniai-api-v1.yaml` — diese Datei ist eine unveränderte Kopie |

## Status

| Bereich | Stand |
|---|---|
| Gesundheit, Fähigkeiten, Einmal-Antworten | implementiert |
| Agent-Läufe und Nutzungsdaten | implementiert; Werkzeuge in Läufen nur mit `claude_sub`, Grenzen siehe [bekannte-luecken.md](../../docs/bekannte-luecken.md) |
| Antwortprüfung gegen JSON-Schema | implementiert (D-020) |
| Nutzungsdaten bei Einmal-Antworten | im Vertrag vorgesehen (`CompletionResponse.usage`), noch nicht geliefert — siehe [bekannte-luecken.md](../../docs/bekannte-luecken.md) |

Umsetzung und Begründung: D-019 in [design-entscheidungen.md](../../docs/design-entscheidungen.md),
Endpunkte in [api-referenz.md](../../docs/api-referenz.md).

## Pflege

1. Änderung zuerst im Master (Backend-Repo), additiv innerhalb von `v1`.
2. Kopie hier im selben Arbeitspaket ersetzen — ohne Änderung der Datei.
3. Version und Status in diesem Dokument und in [../README.md](../README.md) nachziehen.
