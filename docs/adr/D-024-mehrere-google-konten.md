# D-024: Mehrere Google-Konten für Gemini (Abo), Wechsel bei aufgebrauchtem Kontingent

- **Datum:** 28.10.2026
- **Status:** Aktiv (Handprüfung mit zwei echten Konten noch nicht von Hand geprüft — siehe „Handprüfung“)
- **Betrifft:** `providers/gemini_sub_accounts.py`, `providers/gemini_sub_provider.py`, `providers/gemini_sub_login.py`, `app.py` (`/auth/gemini…`), `web/src/components/GoogleLogin.tsx`

## Kontext

Mit D-022 nutzt das Add-on das Kontingent **eines** Google-AI-Pro-Kontos. Das Kontingent erneuert sich
nur alle fünf Stunden und hat ein Wochenlimit; wer viel fragt, stößt daran. Der User will deshalb
**n Konten anmelden** und so das Vielfache an Kontingent nutzen. Jedes Konto ist ein eigenes, bezahltes
Abo.

**Google nennt genau das ausdrücklich nicht unterstützt.** Die FAQ der Antigravity CLI fragt: „Can I
use Antigravity CLI headless mode in third-party coding agents or **automate account switching**?“ und
antwortet: „Wrapping `agy` inside third-party coding agents or applications, **or automating account
rotation**, is not supported under consumer plans.“ (Wortlaut und Quelle in
[recherche.md](../erweiterungen/gemini-provider/recherche.md)). Das ist ein stärkerer Auslöser für
Maßnahmen als der Einsatz von `agy` in D-022 und kann **alle** beteiligten Konten treffen. Der User hat
das Vorhaben am 28.10.2026 trotzdem verlangt; der Hinweis auf diese Klausel ging ihm vor dem Bau zu
und steht in der Oberfläche.

## Betrachtete Optionen

### Option A — Nur ein Konto (Stand D-022)

- Dafür: kein zusätzliches Risiko durch den Wechsel.
- Dagegen: das Kontingent bleibt das eines Kontos — gegen den Auftrag.

### Option B — Ein Heimatverzeichnis je Konto, Wechsel durch anderes `HOME` (gewählt)

- Dafür: Die CLI ist für ein Konto je Zustandsordner gebaut; ein Wechsel ist nur eine andere
  Umgebungsvariable. Keine Datei wird getauscht oder kopiert (das Format der Anmeldung kennt nur die
  CLI, ein eigener Versuch mit geratenem Format scheiterte, D-022). Jedes Konto behält Zustand, Arbeitsbereich
  und Einstellungen für sich; ein kaputtes Konto reißt keines der anderen mit.
- Dagegen: Plattenplatz je Konto (Zustand der CLI, ohne Gespräche, die nach jedem Lauf gelöscht werden);
  die Modellliste müsste je Konto geholt werden — hier gemeinsam, siehe Folgen.

### Option C — Eine Anmeldedatei tauschen

- Dafür: nur ein Zustandsordner.
- Dagegen: Dateien einer fremden Software austauschen, deren Format und Bindung (Installationskennung,
  laufende Prozesse) ungeklärt sind; Wettlauf bei Anfragen; bei einem Absturz mitten im Tausch fehlt
  eine Anmeldung. Verworfen.

## Entscheidung

**Option B.** Jede Anmeldung legt ein neues Konto an: das erste im Basisverzeichnis `/data` (dort lag die
Anmeldung schon vor mehreren Konten, Bestandsinstallationen übernehmen sie als „Konto 1“), jedes weitere
in `/data/omniai-gemini-accounts/konto-N`. Die Liste mit Namen, Reihenfolge und Wartezeiten steht in
`/data/omniai-gemini-accounts.json`; höchstens zehn Konten.

**Wechsel:** Das Add-on nimmt das **erste Konto der Liste, das Kontingent hat**, und bleibt dabei (kein
Reihum). Es wechselt zum nächsten bei (1) aufgebrauchtem Kontingent, (2) von Google eingeschränktem
Konto, (3) ungültig gewordener Anmeldung — und wiederholt dieselbe Anfrage. Eine schlechte Antwort,
ein Zeitlimit oder ein Fehler im Prompt führen **nie** zum Wechsel. Die CLI läuft weiter nur einmal
zugleich.

**Wartezeit:** Ein aufgebrauchtes oder eingeschränktes Konto wird zuerst nach 30 Minuten wieder
versucht, nach jedem weiteren Fehlschlag nach der doppelten Zeit, höchstens nach fünf Stunden (so lange
erneuert sich das Kontingent laut Google). Eine kurze erste Wartezeit nutzt ein früher erneuertes
Kontingent; das Wachstum verhindert, dass jede Anfrage ein leeres Konto antippt. Sind alle Konten in
Wartezeit, antwortet das Add-on sofort mit dem Zeitpunkt des nächsten Versuchs und startet keine CLI.
Ein Konto, bei dem die Anmeldung gelang, aber der Probeauftrag am Kontingent scheiterte, bleibt in der
Liste — mit Wartezeit.

**Keine Tarnung — ausdrücklich.** Das Add-on verbirgt den Wechsel nicht: keine Verteilung der Anfragen
auf Zeiten oder Adressen, kein Verwischen von Gerät, Installationskennung oder Anmeldeumgebung. Es ist
ein Rechner, eine Software, ein offener Wechsel, im Protokoll mit Kontoname zu lesen. Wer Google
täuschen will, bekommt dafür von diesem Projekt nichts. Das ändert nichts daran, dass der Wechsel selbst
von Google nicht unterstützt wird.

## Folgen

- **Positiv:** Das Vielfache an Kontingent, ohne dass der Aufrufer etwas ändern muss; jedes Konto
  für sich entfernbar; kaputte oder leere Konten fallen automatisch aus der Reihe und kehren zurück.
- **Negativ:** Das Risiko durch Googles Haltung steigt mit jedem Konto, und eine Maßnahme kann alle
  Konten treffen. Die Konten teilen eine Modellliste (vom ersten angemeldeten geholt) und müssen
  deshalb demselben Tarif angehören. Die Wartezeit ist geschätzt; die CLI nennt keinen Zeitpunkt für die
  Erneuerung. Der Wechsel hängt am Text „Kontingent aufgebraucht“ der CLI (`QUOTA_MARKER`).
- **Aufwand:** Umgesetzt; Handprüfung mit zwei echten Konten steht aus.

## Handprüfung

| Nr. | Prüfung | Erwartet |
|---|---|---|
| H11 | Zwei Konten anmelden. Viele Anfragen stellen, bis das erste leer ist (Kontingent verbrauchen, oder das erste Konto in Google testweise sperren) | Im Protokoll „Konto … Kontingent aufgebraucht“, „Wechsel auf das nächste Google-Konto“; die Anfrage kommt vom zweiten Konto. Das erste steht in der Liste mit „nächster Versuch“. Weicht die Meldung der CLI ab und es wechselt nichts: `QUOTA_MARKER` ergänzen |
| H12 | Beide Konten leer machen, noch eine Anfrage | Sofort ein Satz mit Uhrzeit des nächsten Versuchs, keine CLI gestartet |
| H13 | Nach der Wartezeit des ersten Kontos fragen | Das erste Konto wird wieder versucht; ist sein Kontingent erneuert, ist es danach wieder „Bereit“ |
| H14 | Die Zugriffsfreigabe des zweiten Kontos in Google widerrufen, dann fragen | Das Konto steht auf „Anmeldung abgelaufen“, die Antwort kommt vom ersten oder die Meldung sagt, dass erneut angemeldet werden muss; Entfernen und neu Anmelden stellt es her |
| H15 | Add-on neu starten, Konto 2 entfernen | Beide Konten überstehen den Neustart; Entfernen löscht nur dessen Ordner unter `/data/omniai-gemini-accounts/` |

## Rücknahmebedingung

Die Entscheidung wird überprüft, wenn eines davon eintritt:

- Google schränkt oder sperrt ein Konto, nachdem mehrere angemeldet waren — Mehrfachanmeldung entfernen
  und den Nutzern sagen, warum.
- Der Wechsel erweist sich als unzuverlässig (H11): Ohne verlässliche Erkennung des leeren Kontos ist
  er nicht zu verantworten.
- Google dokumentiert eine erlaubte Form, mehrere Konten oder Arbeitsbereiche zu nutzen.
