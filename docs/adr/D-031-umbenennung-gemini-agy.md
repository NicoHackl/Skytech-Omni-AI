# D-031: Google Gemini (AGY)

Datum: 29.10.2026. Status: Aktiv.

Der User hat die Umbenennung von `gemini_sub` zu `gemini_agy` und den Anzeigenamen
„Google Gemini (AGY)“ bestätigt. Der neue Web-Anbieter nutzt ebenfalls ein Abo; die
Bezeichnung unterscheidet deshalb den Zugang.

Es gibt keinen Alias. Option, Umgebungsvariablen, Module und Anmelderouten ziehen mit:
`gemini_agy_model`, `GEMINI_AGY_MODEL`, `OMNIAI_GEMINI_AGY_HOME`, `/auth/gemini-agy`.
Die bestehenden Datenpfade bleiben erhalten, damit Konten angemeldet bleiben.
Das bisherige Standardmodell muss neu gewählt werden.

Skytech X und Automationen verwenden laut User den alten Schlüssel nicht. Gespeicherte
Add-on-Optionen müssen auf einen gültigen Anbieter umgestellt werden. Wie der Supervisor
ein Update mit einer inzwischen ungültigen Auswahl behandelt, bleibt ohne Testinstanz
ungeprüft; ein sicherer Ausweg ist, vor dem Update Claude auszuwählen und nach dem
Update Google Gemini (AGY). Der neue Wert lässt sich vor dem Update noch nicht speichern.

D-022 und D-024 dokumentieren weiterhin die damaligen Namen und bekommen einen Verweis hierher.
