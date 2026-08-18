import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/Layout'
import { useToast } from '../components/Toast'
import { providerLabel } from '../provider'
import type { StatusResponse } from '../types'

/* Einstiegsseite: zeigt, womit das Add-on gerade arbeitet und ob es
   einsatzbereit ist. Zu den Zugängen kommt vom Server nur ja/nein — ein
   Schlüssel taucht hier weder ganz noch gekürzt auf. */

/** Reihenfolge der Zugangskacheln, gleich wie im Auswahlfeld der Konfiguration. */
const CREDENTIAL_KEYS = ['claude_sub', 'gemini']

export function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)
  const { toast } = useToast()

  const load = useCallback(
    () =>
      api
        .status()
        .then((value) => {
          setStatus(value)
          setError('')
        })
        .catch((cause: Error) => setError(cause.message)),
    [],
  )

  useEffect(() => {
    void load()
  }, [load])

  async function check() {
    setChecking(true)
    try {
      await load()
      toast('Das Add-on antwortet.')
    } finally {
      setChecking(false)
    }
  }

  const ready = status ? (status.credentials[status.provider] ?? false) : false

  return (
    <>
      <PageHeader
        title="Übersicht"
        subtitle="Zustand des Add-ons"
        actions={
          <button className="btn btn-ghost" onClick={() => void check()} disabled={checking}>
            <Icon name="refresh" size={16} />
            {checking ? 'Wird geprüft…' : 'Verbindung prüfen'}
          </button>
        }
      />
      <div className="content">
        {error ? <div className="alert">{error}</div> : null}

        <div className="welcome-card card">
          <div className="card-body">
            <div className="welcome-icon"><Icon name="dashboard" size={21} /></div>
            <div>
              <h2>Skytech OmniAI</h2>
              <p className="muted">
                {status
                  ? ready
                    ? 'Einsatzbereit. Anfragen können gestellt werden.'
                    : 'Für den aktiven Anbieter ist noch kein Zugang hinterlegt.'
                  : 'Zustand wird abgerufen.'}
              </p>
            </div>
          </div>
        </div>

        {status === null ? (
          <div className="center"><div className="spinner" /></div>
        ) : (
          <>
            {!ready ? (
              <div className="hint-box">
                Damit Anfragen beantwortet werden können, im Add-on unter „Konfiguration“ den
                Zugang für {providerLabel(status.provider)} eintragen und das Add-on neu starten.
              </div>
            ) : null}

            <div className="tiles dashboard-tiles">
              <div className="tile">
                <div className="tile-icon"><Icon name="settings" size={20} /></div>
                <h3>Anbieter</h3>
                <p className="tile-copy">{providerLabel(status.provider)}</p>
              </div>

              <div className="tile">
                <div className="tile-icon"><Icon name="list" size={20} /></div>
                <h3>Standardmodell</h3>
                <p className="tile-copy">{status.default_model ?? 'Der Anbieter entscheidet'}</p>
              </div>

              {CREDENTIAL_KEYS.map((key) => (
                <div className="tile" key={key}>
                  <div className="tile-icon"><Icon name="check" size={20} /></div>
                  <h3>{providerLabel(key)}</h3>
                  <p className="tile-copy">
                    {status.credentials[key] ? (
                      <span className="pill ok">Zugang hinterlegt</span>
                    ) : (
                      <span className="pill muted">Kein Zugang</span>
                    )}
                  </p>
                </div>
              ))}
            </div>

            <div className="card section-card">
              <div className="card-head">
                <h2>Loslegen</h2>
                <div className="sub">Version {status.version ?? '–'}</div>
              </div>
              <div className="card-body">
                <div className="inline-actions">
                  <Link className="btn btn-primary" to="/anfrage">
                    <Icon name="edit" size={16} />Anfrage stellen
                  </Link>
                  <Link className="btn btn-ghost" to="/modelle">
                    <Icon name="list" size={16} />Modelle ansehen
                  </Link>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
