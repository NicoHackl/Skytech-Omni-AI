import { useCallback, useEffect, useRef, useState } from 'react'
import { api, fieldErrorsOf } from '../api'
import { formatWhen } from '../format'
import type { GeminiAccount, GeminiLoginStatus } from '../types'
import { Icon } from './Icon'
import { useToast } from './Toast'

/* Anmeldung der Google-Konten für „Google Gemini (AGY)“ (D-024).

   Die Google-Software hinter dem Anbieter kennt kein Token zum Einfügen. Sie
   gibt eine Adresse aus und wartet etwa eine Minute auf einen Code. Das Add-on
   hält sie dafür offen; hier läuft nur der Weg des Nutzers: Adresse öffnen,
   anmelden, Code kopieren, einfügen. Der Server meldet den Stand, die Seite
   fragt ihn so lange ab, bis nichts mehr läuft.

   Jede Anmeldung legt ein weiteres Konto an. Ist das Kontingent eines Kontos
   aufgebraucht, nimmt das Add-on das nächste; die Liste zeigt, wo jedes steht.

   Die Karte steht im Formular der Einstellungen, ist aber unabhängig vom
   Speichern: jeder Knopf hat type="button", und Enter in einem Feld schickt
   dessen Eingabe, nicht die Einstellungen ab. */

const POLL_MS = 1500
const HURRY_SECONDS = 15

/** Zustandsanzeige eines Kontos: Farbe und Satz. */
function AccountPill({ account }: { account: GeminiAccount }) {
  switch (account.state) {
    case 'ok':
      return <span className="pill ok">Bereit</span>
    case 'exhausted':
      return (
        <span className="pill warn">
          Kontingent aufgebraucht — nächster Versuch {formatWhen(account.retry_at)}
        </span>
      )
    case 'restricted':
      return (
        <span className="pill err">
          Von Google eingeschränkt — nächster Versuch {formatWhen(account.retry_at)}
        </span>
      )
    case 'login_expired':
      return <span className="pill err">Anmeldung abgelaufen</span>
    default:
      return <span className="pill muted">Nicht angemeldet</span>
  }
}

export function GoogleLogin({
  locked,
  onModelsChange,
}: {
  locked: boolean
  /** Die Liste der Modelle hat sich geändert; die Seite lädt sie neu. */
  onModelsChange?: () => void
}) {
  const [status, setStatus] = useState<GeminiLoginStatus | null>(null)
  const [error, setError] = useState('')
  const [label, setLabel] = useState('')
  const [labelError, setLabelError] = useState('')
  const [code, setCode] = useState('')
  const [codeError, setCodeError] = useState('')
  const [busy, setBusy] = useState(false)
  const [deadline, setDeadline] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const previousState = useRef<string>('idle')
  const { toast } = useToast()

  const adopt = useCallback(
    (next: GeminiLoginStatus) => {
      // Eine Prüfung, die gerade zu Ende gegangen ist, bekommt eine Rückmeldung.
      if (previousState.current === 'checking' && next.state === 'idle') {
        if (next.error) toast('Die Anmeldung hat nicht geklappt.', 'err')
        else toast('Konto angemeldet.')
      }
      previousState.current = next.state
      setStatus(next)
      setDeadline(
        next.state === 'waiting' && next.seconds_left !== null
          ? Date.now() + next.seconds_left * 1000
          : null,
      )
      if (next.state !== 'waiting') setCode('')
    },
    [toast],
  )

  const refresh = useCallback(
    () =>
      api
        .geminiLogin()
        .then(adopt)
        .catch((cause: Error) => setError(cause.message)),
    [adopt],
  )

  useEffect(() => {
    void refresh()
  }, [refresh])

  const state = status?.state ?? 'idle'

  // Solange eine Anmeldung läuft, den Stand abfragen und den Rest der Zeit mitzählen.
  useEffect(() => {
    if (state === 'idle') return
    const poll = window.setInterval(() => void refresh(), POLL_MS)
    const tick = window.setInterval(() => setNow(Date.now()), 1000)
    return () => {
      window.clearInterval(poll)
      window.clearInterval(tick)
    }
  }, [state, refresh])

  // Ein Konto, das gerade dazukam oder wegfiel, ändert, was die Modelle zeigen können.
  const accountCount = status?.accounts.length ?? 0
  const previousCount = useRef<number | null>(null)
  useEffect(() => {
    if (status === null) return
    if (previousCount.current !== null && previousCount.current !== accountCount) onModelsChange?.()
    previousCount.current = accountCount
  }, [status, accountCount, onModelsChange])

  async function run(action: () => Promise<GeminiLoginStatus>) {
    setBusy(true)
    setError('')
    setCodeError('')
    setLabelError('')
    try {
      adopt(await action())
    } catch (cause) {
      const fields = fieldErrorsOf(cause)
      if (fields.code) setCodeError(fields.code)
      else if (fields.label) setLabelError(fields.label)
      else setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function startLogin() {
    void run(() => api.geminiLoginStart(label.trim()))
    setLabel('')
  }

  function submitCode() {
    if (code.trim() === '') {
      setCodeError('Bitte den Code von Google einfügen.')
      return
    }
    void run(() => api.geminiLoginCode(code))
  }

  async function reloadModels() {
    setBusy(true)
    setError('')
    try {
      const { models } = await api.geminiModelsRefresh()
      onModelsChange?.()
      if (models.length > 0) toast(`${models.length} Modelle gefunden.`)
      else toast('Es wurden keine Modelle gefunden. Die Ausgabe steht im Protokoll des Add-ons.', 'err')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function removeAccount(account: GeminiAccount) {
    if (!window.confirm(`Das Konto „${account.label}“ wirklich entfernen?`)) return
    void run(() => api.geminiLogout(account.id))
  }

  const secondsLeft = deadline === null ? null : Math.max(0, Math.ceil((deadline - now) / 1000))
  const disabled = locked || busy
  const accounts = status?.accounts ?? []

  return (
    <section className="card">
      <div className="card-head">
        <h2>Google-Anmeldung (AGY)</h2>
        <div className="sub">
          Für „Google Gemini (AGY)“ — nutzt das Kontingent von Google AI Pro, auf Wunsch mit mehreren
          Konten
        </div>
      </div>
      <div className="card-body">
        <div className="hint-box">
          Google unterstützt die Nutzung eines privaten Abos über andere Anwendungen nicht und kann
          Konten dafür einschränken oder sperren. Das automatische Wechseln zwischen mehreren Konten
          nennt Google dabei ausdrücklich als nicht unterstützt: mit jedem weiteren Konto steigt das
          Risiko, und eine Maßnahme kann alle treffen. Die Nutzung geschieht auf eigenes Risiko; am
          besten dienen Konten, deren Verlust nicht schmerzt.
        </div>

        {error ? <div className="alert">{error}</div> : null}
        {status?.error ? <div className="alert">{status.error}</div> : null}

        {status === null ? (
          error ? null : <div className="center"><div className="spinner" /></div>
        ) : !status.available ? (
          <div className="alert">
            Diese Anmeldung ist in diesem Add-on nicht verfügbar. Das Add-on wurde vermutlich
            unvollständig gebaut — bitte neu installieren.
          </div>
        ) : (
          <>
            {accounts.length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Konto</th>
                      <th>Zustand</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map((account, index) => (
                      <tr key={account.id}>
                        <td className="cell-title">
                          {account.label}
                          <div className="cell-sub">{index === 0 ? 'Zuerst an der Reihe' : 'Danach'}</div>
                        </td>
                        <td><AccountPill account={account} /></td>
                        <td className="row-actions">
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => removeAccount(account)}
                            disabled={disabled || state !== 'idle'}
                          >
                            <Icon name="trash" size={14} />
                            Entfernen
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {state === 'checking' ? (
              <div className="center">
                <div className="spinner" />
                <p>Google prüft die Anmeldung. Das dauert einen Moment.</p>
              </div>
            ) : state === 'waiting' ? (
              <div className="form-grid">
                <div className="field wide">
                  <span>1. Bei Google anmelden{status.pending_label ? ` (${status.pending_label})` : ''}</span>
                  <small>Mit dem Konto, das Google AI Pro hat.</small>
                  <div className="inline-actions">
                    <a
                      className="btn btn-primary"
                      href={status.url ?? undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Icon name="external" size={16} />
                      Google-Seite öffnen
                    </a>
                  </div>
                </div>

                <div className={`field wide${codeError ? ' invalid' : ''}`}>
                  <span>
                    <label htmlFor="google-login-code">2. Code einfügen</label>{' '}
                    {secondsLeft !== null ? (
                      <span className={`pill ${secondsLeft <= HURRY_SECONDS ? 'warn' : 'muted'}`}>
                        Noch {secondsLeft} s
                      </span>
                    ) : null}
                  </span>
                  <input
                    id="google-login-code"
                    type="text"
                    value={code}
                    onChange={(event) => {
                      setCode(event.target.value)
                      setCodeError('')
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        submitCode()
                      }
                    }}
                    disabled={disabled}
                    autoComplete="off"
                    spellCheck={false}
                    placeholder="Code von Google"
                  />
                  <small>
                    Google zeigt ihn nach der Anmeldung an. Er gilt nur kurz — am besten vorher im
                    Browser bei Google angemeldet sein.
                  </small>
                  {codeError ? <small className="field-error">{codeError}</small> : null}
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={submitCode}
                      disabled={disabled}
                    >
                      <Icon name="check" size={16} />
                      Anmeldung abschließen
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => void run(() => api.geminiLoginCancel())}
                      disabled={locked}
                    >
                      Abbrechen
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className={`field${labelError ? ' invalid' : ''}`}>
                <span>
                  <label htmlFor="google-login-label">
                    {accounts.length === 0 ? 'Konto anmelden' : 'Weiteres Konto anmelden'}
                  </label>
                </span>
                <input
                  id="google-login-label"
                  type="text"
                  value={label}
                  onChange={(event) => {
                    setLabel(event.target.value)
                    setLabelError('')
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      if (!disabled) startLogin()
                    }
                  }}
                  disabled={disabled}
                  autoComplete="off"
                  maxLength={40}
                  placeholder={`Name des Kontos (optional, sonst „Konto ${accounts.length + 1}“)`}
                />
                <small>
                  {accounts.length === 0
                    ? 'Die Anmeldung geschieht einmal; das Add-on speichert sie und erneuert sie selbst.'
                    : 'Das Add-on nimmt das nächste Konto, sobald das Kontingent des vorigen aufgebraucht ist.'}
                </small>
                {labelError ? <small className="field-error">{labelError}</small> : null}
                <div className="inline-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={startLogin}
                    disabled={disabled}
                  >
                    <Icon name="external" size={16} />
                    Mit Google anmelden
                  </button>
                  {status.signed_in ? (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => void reloadModels()}
                      disabled={disabled}
                    >
                      <Icon name="refresh" size={16} />
                      Modelle neu laden
                    </button>
                  ) : null}
                </div>
              </div>
            )}
            {accounts.length > 0 ? (
              <div className="field">
                <small>
                  „Entfernen“ löscht die Anmeldung aus dem Add-on; den Zugriff selbst lässt sich
                  zusätzlich im Google-Konto unter „Sicherheit“ widerrufen.
                </small>
              </div>
            ) : null}
          </>
        )}
      </div>
    </section>
  )
}
