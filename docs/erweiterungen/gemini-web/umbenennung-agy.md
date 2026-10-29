# Umbenennung: `gemini_sub` wird zu „Gemini AGY“

> Umgesetzt, siehe [D-031](../../adr/D-031-umbenennung-gemini-agy.md).
> Der User hat Namen, Schlüssel und Erhalt der Datenpfade bestätigt. Die folgende
> Tabelle hält den Umfang fest. Vor dem Update kann der neue Wert noch nicht gewählt
> werden: vorübergehend Claude wählen, erst nach dem Update AGY einstellen.

## Warum

Der Name „Abo“ passt nicht mehr: Auch der neue Anbieter Gemini Web nutzt ein Abo. Unterscheiden
soll künftig der Weg, nicht das Wort „Abo“ — der eine geht über die Antigravity-CLI (`agy`), der
andere über die Web-App.

## Was sich geändert hat

| Was | Alt | Neu |
|---|---|---|
| Anzeigename | Google Gemini (Abo) | Google Gemini (AGY) |
| Schlüssel des Anbieters (`provider`, `/ask`, `/v1`) | `gemini_sub` | `gemini_agy` |
| Add-on-Option des Standardmodells | `gemini_sub_model` | `gemini_agy_model` |
| Umgebungsvariable dazu | `GEMINI_SUB_MODEL` | `GEMINI_AGY_MODEL` |
| Umgebungsvariable des Zustandsordners | `OMNIAI_GEMINI_HOME` | `OMNIAI_GEMINI_AGY_HOME` |
| Module | `providers/gemini_sub_provider.py`, `gemini_sub_login.py`, `gemini_sub_accounts.py` | `gemini_agy_provider.py`, `gemini_agy_login.py`, `gemini_agy_accounts.py` |
| Klassen und Konstanten | `GeminiSubProvider`, `GEMINI_SUB_MODELS`, `GEMINI_SUB_MODEL_PATTERN`, `gemini_sub_models`, `gemini_sub_signed_in`, `gemini_sub_refresh_models` | `GeminiAgyProvider`, `GEMINI_AGY_MODELS`, `GEMINI_AGY_MODEL_PATTERN`, `gemini_agy_models`, `gemini_agy_signed_in`, `gemini_agy_refresh_models` |
| Routen der Anmeldung | `/auth/gemini`, `/auth/gemini/start`, `/code`, `/cancel`, `/models`, `/konto…`, `DELETE /auth/gemini/<id>` | `/auth/gemini-agy…` (gleiche Unterpfade) |
| Bereich in der Seitenleiste | „Google Gemini (Abo)“, Adresse `…/einstellungen/gemini-abo` | „Google Gemini (AGY)“, Adresse `…/einstellungen/gemini-agy` |
| Tests | `test_gemini_sub_*.py`, Verweise in `test_app.py`, `test_api_v1.py`, `test_settings.py`, `test_factory.py` | `test_gemini_agy_*.py`, angepasste Verweise |
| Oberfläche | `provider.ts` (Klarname, `SUBSCRIPTION_PROVIDER`), `types.ts` (`ProviderName`, `gemini_sub_model`), `api.ts`, `GoogleLogin.tsx`, `Allgemein.tsx`, `Dashboard.tsx`, `settingsSections.ts` | entsprechend |
| Konfiguration | `config.yaml`: `provider`-Liste, Option und Kommentare; `settings.py`, `config_loader.py`, `factory.py` | entsprechend |
| Doku | `README.md`, `info.md`, `architektur.md`, `konfiguration.md`, `api-referenz.md`, `bekannte-luecken.md`, `frontend.md`, `roadmap.md`, `sicherheit-datenschutz.md`, `design-entscheidungen.md` | Namen ersetzt; je Datei durchlesen, nicht blind ersetzen |

Umfang heute (Zählung vom 29.10.2026): `gemini_sub` kommt in rund 30 Dateien vor, der Anzeigename
„Google Gemini (Abo)“ in rund 28.

## Was ausdrücklich bleibt

| Was | Grund |
|---|---|
| **Datenpfade:** `/data/.gemini`, `/data/omniai-gemini-accounts.json`, `/data/omniai-gemini-accounts/konto-N`, `omniai-gemini-workspace` | Sie umzubenennen hieße, dass jeder Nutzer **alle Konten neu anmelden** muss. Die Namen sind intern und nirgends sichtbar. Der Preis wäre hoch, der Nutzen null (Vorschlag in F2) |
| **Texte in D-022 und D-024** | ADRs halten Entscheidungen zu ihrem Zeitpunkt fest. Beide bekommen oben **einen Hinweis** („Der Anbieter heißt seit D-031 `gemini_agy`“), der Text bleibt |
| **`skytech_omniai/CHANGELOG.md`** | Von der CI geschrieben, nie von Hand (eiserne Regel 1) |
| **Vertrag v1** (`contract/contract_skytech_x_omniai/omniai-api-v1.yaml`) | Dort kommt `gemini_sub` nicht vor (**geprüft** per Suche am 29.10.2026); `provider` ist eine offene Menge. Die Datei bleibt wortgleich mit dem Master |
| **Logik** | Rein Umbenennung. Kein Verhalten ändert sich |

## Folgen — ohne Übergang

Der User hat „ohne Übergang“ gewählt. Das heißt:

- **Wer `provider: gemini_sub` gespeichert hat**, hat nach dem Update einen Wert, den das Schema nicht
  mehr kennt. Erwartet wird, dass Home Assistant die Konfiguration ablehnt, bis der Anbieter umgestellt
  ist — **ungeprüft**, der [Spike](umsetzungsplan.md#ap-2--spike) stellt es nach. Das Add-on selbst kann
  das nicht abfangen, weil die Prüfung vor seinem Start liegt.
- **`gemini_sub_model`** (Option) wird beim Update nicht übernommen; ein gesetztes Standardmodell
  geht verloren und ist neu zu wählen. Die Anmeldungen der Konten **bleiben**, weil die Datenpfade
  bleiben.
- **Aufrufer, die `provider: "gemini_sub"` schicken** (Skytech X, Automationen), bekommen von `/ask`
  und `/v1` die Meldung „Der Anbieter … ist nicht verfügbar“ mit der Liste der gültigen. Das Add-on
  nimmt den alten Namen **nicht** mehr an.
- **Gegenmaßnahmen, die keinen Übergang bedeuten:** Ein `Changelog-Geändert`-Eintrag, der das sagt
  („Vor dem Update den Anbieter auf Gemini AGY umstellen, sonst startet das Add-on nicht“), und eine
  Benachrichtigung an Skytech X vor dem Merge des Pull Requests nach `main`. Der Merge ist ein Release
  an alle Nutzer (D-025).

## Vorgehen (siehe [AP 1](umsetzungsplan.md#ap-1--umbenennung))

1. Offene Fragen F1, F2, F5 beantwortet haben.
2. Module mit `git mv` umbenennen, damit die Historie erhalten bleibt, danach Bezeichner.
3. Je Datei lesen und anpassen, kein Massenersatz: „Abo“ steht auch in Sätzen, die **richtig** bleiben
   (etwa „Claude (Abo)“, „ChatGPT (Abo)“).
4. Prüfung: Suche nach `gemini_sub` und `Gemini (Abo)` findet nur noch ADRs und `CHANGELOG.md`.
5. `scripts/check.sh`, danach `scripts/check.sh --docker`, danach Seitenleiste in beiden Modi ansehen.
6. ADR **D-031** (Umbenennung, Folgen, Grund für das Beibehalten der Datenpfade).
