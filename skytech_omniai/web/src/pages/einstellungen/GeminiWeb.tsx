import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api'
import { formatWhen } from '../../format'
import { useToast } from '../../components/Toast'
import type { GeminiWebStatus } from '../../types'
import { useSettingsForm } from './form'

export function GeminiWeb() {
  const { readOnly, reloadCatalog } = useSettingsForm()
  const { toast } = useToast()
  const [status, setStatus] = useState<GeminiWebStatus | null>(null)
  const [label, setLabel] = useState('')
  const [psid, setPsid] = useState('')
  const [psidts, setPsidts] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const load = useCallback(() => api.geminiWebStatus().then(setStatus), [])
  useEffect(() => { void load().catch((cause: Error) => setError(cause.message)) }, [load])

  async function action(work: () => Promise<unknown>, message: string) {
    setBusy(true)
    setError('')
    try {
      await work()
      await load()
      reloadCatalog()
      toast(message)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function signIn() {
    if (busy || readOnly || !psid || !psidts) return
    const input = { label, psid, psidts }
    // Auch bei Fehlern bleiben Anmeldewerte nach dem Absenden nicht im Formular.
    setPsid('')
    setPsidts('')
    void action(() => api.geminiWebAdd(input), 'Das Google-Konto ist angemeldet.')
  }

  const locked = readOnly || busy
  return (
    <section className="card">
      <div className="card-head">
        <h2>Google Gemini (Web)</h2>
        <div className="sub">Nutzt das Kontingent der Gemini-Web-App</div>
      </div>
      <div className="card-body">
        <div className="hint-box">
          Google erlaubt diese Nutzung nicht und kann das Konto einschränken oder sperren.
          Verwende nur ein separates Konto, dessen Verlust du verschmerzen kannst, ohne persönliche
          Daten und ohne Verbindungen zu Gmail oder Drive. Anfragen und Anhänge gehen an Google.
          Änderungen bei Google können diesen Zugang jederzeit unterbrechen. Die Werkzeugauswahl
          des Add-ons hat hier keine Wirkung.
        </div>
        {error ? <div className="alert" role="alert">{error}</div> : null}
        {status === null ? <div className="center"><div className="spinner" /></div> : (
          status.accounts.length === 0 ? <div className="empty">Noch kein Google-Konto angemeldet. Füge unten die Anmeldewerte ein.</div> : (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Konto</th><th>Zustand</th><th>Aktion</th></tr></thead>
                <tbody>{status.accounts.map((account) => (
                  <tr key={account.id}>
                    <td className="cell-title">{account.label}</td>
                    <td><span className={`pill ${account.state === 'ok' ? 'ok' : 'warn'}`}>
                      {account.state === 'ok' ? 'Bereit' : account.state === 'exhausted'
                        ? `Kontingent aufgebraucht — nächster Versuch ${formatWhen(account.retry_at)}`
                        : 'Anmeldung abgelaufen'}
                    </span></td>
                    <td><button type="button" className="btn btn-danger btn-sm" disabled={locked}
                      onClick={() => {
                        if (window.confirm(`„${account.label}“ wirklich entfernen?`)) {
                          void action(() => api.geminiWebRemove(account.id), 'Das Google-Konto wurde entfernt.')
                        }
                      }}>Entfernen</button></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )
        )}
        <details className="advanced-card">
          <summary>Anmeldewerte kopieren</summary>
          <ol>
            <li>Öffne gemini.google.com in einem privaten Browserfenster und melde das separate Konto an.</li>
            <li>Öffne die Entwicklerwerkzeuge und dort unter „Anwendung“ bzw. „Speicher“ die Cookies für Google.</li>
            <li>Kopiere den Wert von <code>__Secure-1PSID</code> in das erste Feld und den von <code>__Secure-1PSIDTS</code> in das zweite.</li>
            <li>Schließe das private Fenster anschließend, ohne dich vorher bei Google abzumelden. Nutze das Konto danach möglichst nur hier.</li>
          </ol>
          <p>Diese Werte gewähren Zugriff auf das Konto. Gib sie niemandem weiter. Bei abgelaufener Anmeldung das Konto hier entfernen und erneut anmelden.</p>
          <p>Jede Anfrage startet einen neuen temporären Chat. Google kann Eingaben trotzdem nach seinen Datenbedingungen verarbeiten.</p>
          <p>Dieser Zugang verwendet die Bibliothek <a href="https://github.com/HanaokaYuzu/Gemini-API" target="_blank" rel="noreferrer">gemini-webapi</a> unter AGPL-3.0. Lizenz und Quelltext liegen im Add-on bei.</p>
        </details>
        <div className="form-grid" onKeyDown={(event) => {
          if (event.key === 'Enter') { event.preventDefault(); signIn() }
        }}>
          <label className="field wide"><span>Name des Kontos</span>
            <input value={label} maxLength={40} autoComplete="off" disabled={locked}
              onChange={(event) => setLabel(event.target.value)} placeholder="Zum Beispiel Hausautomation" />
          </label>
          <label className="field"><span>Erster Anmeldewert</span>
            <input type="password" value={psid} autoComplete="off" spellCheck={false} disabled={locked}
              onChange={(event) => setPsid(event.target.value)} />
          </label>
          <label className="field"><span>Zweiter Anmeldewert</span>
            <input type="password" value={psidts} autoComplete="off" spellCheck={false} disabled={locked}
              onChange={(event) => setPsidts(event.target.value)} />
          </label>
        </div>
        <div className="inline-actions">
          <button type="button" className="btn btn-primary" disabled={locked || !psid || !psidts}
            onClick={signIn}>{busy ? 'Wird geprüft…' : 'Konto anmelden'}</button>
          <button type="button" className="btn btn-ghost" disabled={locked || !status?.accounts.length}
            onClick={() => void action(api.geminiWebModelsRefresh, 'Die Modellliste wurde neu geladen.')}>
            Modelle neu laden
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy}
            onClick={() => void action(load, 'Die Kontenliste wurde neu geladen.')}>Liste neu laden</button>
        </div>
        <p className="muted">Bis zu zehn Konten. Das erste mit verfügbarem Kontingent wird verwendet; weitere Konten erhöhen das Sperrrisiko.</p>
      </div>
    </section>
  )
}
