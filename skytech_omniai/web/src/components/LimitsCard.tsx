import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { formatNumber, formatWhen } from '../format'
import { limitStateLabel, limitWindowLabel, providerLabel } from '../provider'
import type { LimitAccount, LimitWindow, LimitsResponse } from '../types'
import { Icon } from './Icon'

/* Karte „Kontingente“ auf der Übersicht (D-033): je Anbieter und Konto, wie viel
   vom Abo verbraucht ist und wann es wieder frei wird. Geladen wird beim Öffnen
   und auf Knopfdruck — kein Abruf im Takt, weil die Abfrage bei ChatGPT jedes
   Mal kurz einen eigenen Prozess startet. Unbekannt bleibt unbekannt: ohne
   Prozentwert gibt es keinen Balken, nie einen leeren als „0 %“. */

/** Ab hier wird der Balken gelb, ab 100 % rot. */
const WARN_PERCENT = 80

function meterTone(used: number): 'ok' | 'warn' | 'err' {
  if (used >= 100) return 'err'
  return used >= WARN_PERCENT ? 'warn' : 'ok'
}

/** Erklärung, wenn ein Konto keinen Balken hat — was der Nutzer daraus macht. */
function emptyNote(account: LimitAccount): string {
  switch (account.state) {
    case 'unavailable':
      return 'Für eine Anzeige in den Einstellungen einen Zugang eintragen.'
    case 'login_required':
      return 'Bitte in den Einstellungen neu anmelden.'
    case 'unknown':
      if (account.provider === 'claude_sub') {
        return 'Noch kein Stand. Claude meldet das Kontingent mit der nächsten Anfrage.'
      }
      return 'Das Kontingent ließ sich gerade nicht abfragen. Bitte später aktualisieren.'
    case 'ok':
      if (account.provider === 'gemini' || account.provider === 'codex_sub') {
        return 'Abrechnung nach Verbrauch über den API-Schlüssel, ohne festes Kontingent.'
      }
      if (account.provider === 'gemini_agy' || account.provider === 'gemini_web') {
        return 'Google nennt keinen Verbrauch, nur ob das Konto bereit ist.'
      }
      return 'Kein Verbrauch gemeldet.'
    default:
      return ''
  }
}

function WindowRow({ window, extraBucket }: { window: LimitWindow; extraBucket: boolean }) {
  const label = limitWindowLabel(window.id, window.durationMinutes) +
    (extraBucket ? ' (weiteres Kontingent)' : '')
  const used = window.usedPercent
  return (
    <div className="limit-window">
      <div className="limit-window-head">
        <span>{label}</span>
        <span className="muted">
          {used === null ? 'Verbrauch unbekannt' : `${formatNumber(used)} % verbraucht`}
        </span>
      </div>
      {used === null ? null : (
        <div
          className="meter"
          role="progressbar"
          aria-label={`${label}: verbraucht`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(Math.min(used, 100))}
        >
          {/* Breite ist ein berechneter Wert — der einzige zulässige Inline-Style. */}
          <div
            className={`meter-fill ${meterTone(used)}`}
            style={{ width: `${Math.max(0, Math.min(used, 100))}%` }}
          />
        </div>
      )}
      {window.resetsAt ? (
        <div className="limit-note">Neues Kontingent ab {formatWhen(window.resetsAt)}</div>
      ) : null}
    </div>
  )
}

function AccountRow({ account }: { account: LimitAccount }) {
  const state = limitStateLabel(account.state)
  const name = account.label
    ? `${providerLabel(account.provider)} · ${account.label}`
    : providerLabel(account.provider)
  const firstBucket = account.windows[0]?.limitId ?? null
  const observed = account.windows.some((window) => window.source === 'observed')
  return (
    <div className="limit-account">
      <div className="limit-account-head">
        <strong>{name}</strong>
        <span className={`pill ${state.tone}`}>{state.text}</span>
      </div>
      {account.retryAt ? (
        <div className="limit-note">
          {account.retryAtSource === 'estimated' ? 'Nächster Versuch ab ' : 'Wieder verfügbar ab '}
          {formatWhen(account.retryAt)}
        </div>
      ) : null}
      {account.windows.length === 0 ? (
        <div className="limit-note">{emptyNote(account)}</div>
      ) : (
        account.windows.map((window) => (
          <WindowRow
            key={`${window.limitId ?? ''}-${window.id}`}
            window={window}
            extraBucket={window.limitId !== firstBucket}
          />
        ))
      )}
      {observed && account.observedAt ? (
        <div className="limit-note">Zuletzt gemeldet: {formatWhen(account.observedAt)}</div>
      ) : null}
    </div>
  )
}

export function LimitsCard() {
  const [data, setData] = useState<LimitsResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.limits())
      setError('')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="card section-card">
      <div className="card-head">
        <h2>Kontingente</h2>
        {data ? <div className="sub">Stand {formatWhen(data.measuredAt)}</div> : null}
        <div className="spacer" />
        <button className="btn btn-ghost btn-sm" onClick={() => void load()} disabled={loading}>
          <Icon name="refresh" size={14} />
          {loading ? 'Wird aktualisiert…' : 'Aktualisieren'}
        </button>
      </div>
      <div className="card-body">
        {error ? <div className="alert">{error}</div> : null}
        {data === null ? (
          error ? null : <div className="center"><div className="spinner" /></div>
        ) : data.accounts.length === 0 ? (
          <div className="empty">
            <Icon name="info" size={28} />
            <p>Noch kein Anbieter eingerichtet.</p>
            <Link className="btn btn-primary" to="/einstellungen">Zu den Einstellungen</Link>
          </div>
        ) : (
          <div className="limit-list">
            {data.accounts.map((account) => (
              <AccountRow key={`${account.provider}-${account.accountRef}`} account={account} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
