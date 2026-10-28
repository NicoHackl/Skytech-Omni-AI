import { useCallback, useEffect, useRef, useState } from 'react'
import { api, fieldErrorsOf } from '../api'
import type { GeminiLoginStatus } from '../types'
import { Icon } from './Icon'
import { useToast } from './Toast'

/* Anmeldung des Google-Kontos für „Google Gemini (Abo)“.

   Die Google-Software hinter dem Anbieter kennt kein Token zum Einfügen. Sie
   gibt eine Adresse aus und wartet etwa eine Minute auf einen Code. Das Add-on
   hält sie dafür offen; hier läuft nur der Weg des Nutzers: Adresse öffnen,
   anmelden, Code kopieren, einfügen. Der Server meldet den Stand, die Seite
   fragt ihn so lange ab, bis nichts mehr läuft.

   Die Karte steht im Formular der Einstellungen, ist aber unabhängig vom
   Speichern: jeder Knopf hat type="button", und Enter im Codefeld schickt den
   Code, nicht die Einstellungen ab. */

const POLL_MS = 1500
const HURRY_SECONDS = 15

export function GoogleLogin({ locked }: { locked: boolean }) {
  const [status, setStatus] = useState<GeminiLoginStatus | null>(null)
  const [error, setError] = useState('')
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
        if (next.signed_in) toast('Bei Google angemeldet.')
        else toast('Die Anmeldung hat nicht geklappt.', 'err')
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

  async function run(action: () => Promise<GeminiLoginStatus>) {
    setBusy(true)
    setError('')
    setCodeError('')
    try {
      adopt(await action())
    } catch (cause) {
      const fields = fieldErrorsOf(cause)
      if (fields.code) setCodeError(fields.code)
      else setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function submitCode() {
    if (code.trim() === '') {
      setCodeError('Bitte den Code von Google einfügen.')
      return
    }
    void run(() => api.geminiLoginCode(code))
  }

  function logout() {
    if (!window.confirm('Die Google-Anmeldung wirklich entfernen?')) return
    void run(() => api.geminiLogout())
  }

  const secondsLeft = deadline === null ? null : Math.max(0, Math.ceil((deadline - now) / 1000))
  const disabled = locked || busy

  return (
    <section className="card section-card">
      <div className="card-head">
        <h2>Google-Anmeldung (Abo)</h2>
        <div className="sub">Für „Google Gemini (Abo)“ — nutzt das Kontingent von Google AI Pro</div>
      </div>
      <div className="card-body">
        <div className="hint-box">
          Google unterstützt die Nutzung eines privaten Abos über andere Anwendungen nicht und kann
          Konten dafür einschränken oder sperren. Die Nutzung geschieht auf eigenes Risiko; am
          besten dient ein Konto, dessen Verlust nicht schmerzt.
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
        ) : state === 'checking' ? (
          <div className="center">
            <div className="spinner" />
            <p>Google prüft die Anmeldung. Das dauert einen Moment.</p>
          </div>
        ) : state === 'waiting' ? (
          <div className="form-grid">
            <div className="field wide">
              <span>1. Bei Google anmelden</span>
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
                <button type="button" className="btn btn-primary" onClick={submitCode} disabled={disabled}>
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
        ) : status.signed_in ? (
          <div className="field">
            <span>
              Status <span className="pill ok">Angemeldet</span>
            </span>
            <small>
              „Google Gemini (Abo)“ ist einsatzbereit. Abmelden entfernt die Anmeldung aus dem
              Add-on; den Zugriff selbst lässt sich zusätzlich im Google-Konto unter „Sicherheit“
              widerrufen.
            </small>
            <div className="inline-actions">
              <button type="button" className="btn btn-danger btn-sm" onClick={logout} disabled={disabled}>
                <Icon name="logout" size={14} />
                Abmelden
              </button>
            </div>
          </div>
        ) : (
          <div className="field">
            <span>
              Status <span className="pill muted">Nicht angemeldet</span>
            </span>
            <small>
              Die Anmeldung geschieht einmal; das Add-on speichert sie und erneuert sie selbst.
            </small>
            <div className="inline-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void run(() => api.geminiLoginStart())}
                disabled={disabled}
              >
                <Icon name="external" size={16} />
                Mit Google anmelden
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
