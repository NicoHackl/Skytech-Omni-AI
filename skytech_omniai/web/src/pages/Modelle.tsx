import { useEffect, useState } from 'react'
import { api } from '../api'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/Layout'
import { providerLabel } from '../provider'
import type { ModelsResponse } from '../types'

/* Übersicht der auswählbaren Modelle je Anbieter. Dieselbe Quelle, die auch
   Automatisierungen abfragen können — damit steht die Liste nur an einer
   Stelle und läuft nicht auseinander. */

export function Modelle() {
  const [catalog, setCatalog] = useState<ModelsResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .models()
      .then((value) => {
        if (!cancelled) setCatalog(value)
      })
      .catch((cause: Error) => {
        if (!cancelled) setError(cause.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <PageHeader title="Modelle" subtitle="Was sich pro Anfrage auswählen lässt" />
      <div className="content">
        {error ? <div className="alert">{error}</div> : null}

        <div className="info-strip">
          <Icon name="info" size={18} />
          <span>
            Die Auswahl in der Konfiguration legt nur den Standard fest. Pro Anfrage lässt sich
            jedes Modell des jeweiligen Anbieters setzen.
          </span>
        </div>

        {catalog === null ? (
          <div className="center"><div className="spinner" /></div>
        ) : (
          Object.entries(catalog.providers).map(([key, entry]) => (
            <div className="card section-card" key={key}>
              <div className="card-head">
                <h2>{providerLabel(key)}</h2>
                <div className="sub">{key === catalog.active_provider ? 'Aktiv' : 'Nicht aktiv'}</div>
              </div>
              {entry.models.length === 0 ? (
                <div className="empty">
                  <Icon name="list" size={40} />
                  <p>Für diesen Anbieter ist kein Modell hinterlegt.</p>
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr><th>Modell</th><th>Rolle</th></tr>
                    </thead>
                    <tbody>
                      {entry.models.map((name) => (
                        <tr key={name}>
                          <td className="cell-title mono">{name}</td>
                          <td>
                            {name === entry.default ? (
                              <span className="pill primary">Standard</span>
                            ) : (
                              <span className="pill muted">Auswählbar</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </>
  )
}
