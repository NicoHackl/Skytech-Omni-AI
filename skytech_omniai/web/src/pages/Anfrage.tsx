import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/Layout'
import { useToast } from '../components/Toast'
import { MODEL_AUTO, providerLabel } from '../provider'
import type { ModelsResponse } from '../types'

/* Testanfrage an den gewählten Anbieter. Die Antwort ist das JSON des Modells
   und wird deshalb als Rohtext gezeigt — hier ist der Aufbau vorher nicht
   bekannt, und genau dieser Aufbau ist das, was der Nutzer sehen will. */

export function Anfrage() {
  const [catalog, setCatalog] = useState<ModelsResponse | null>(null)
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState(MODEL_AUTO)
  const [prompt, setPrompt] = useState('')
  const [running, setRunning] = useState(false)
  const [answer, setAnswer] = useState<string | null>(null)
  const [error, setError] = useState('')
  const { toast } = useToast()

  useEffect(() => {
    let cancelled = false
    api
      .models()
      .then((value) => {
        if (cancelled) return
        setCatalog(value)
        setProvider(value.active_provider)
      })
      .catch((cause: Error) => {
        if (!cancelled) setError(cause.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function changeProvider(next: string) {
    setProvider(next)
    // Das Modell gehört zum Anbieter: beim Wechsel würde eine stehengebliebene
    // Auswahl nicht mehr passen und der Server sie zu Recht ablehnen.
    setModel(MODEL_AUTO)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setRunning(true)
    setError('')
    try {
      const result = await api.ask({
        prompt,
        provider: provider || undefined,
        model: model === MODEL_AUTO ? undefined : model,
      })
      setAnswer(JSON.stringify(result, null, 2))
      toast('Die Antwort ist da.')
    } catch (cause) {
      setAnswer(null)
      setError((cause as Error).message)
      toast('Die Anfrage ist fehlgeschlagen.', 'err')
    } finally {
      setRunning(false)
    }
  }

  const models = catalog?.providers[provider]?.models ?? []

  return (
    <>
      <PageHeader title="Anfrage" subtitle="Eine Testanfrage an das Modell stellen" />
      <div className="content form-content">
        {error ? <div className="alert">{error}</div> : null}

        <form className="card" onSubmit={(event) => void submit(event)}>
          <div className="card-head">
            <h2>Anfrage</h2>
            <div className="sub">Die Antwort kommt als JSON zurück</div>
          </div>
          <div className="card-body">
            <div className="form-grid">
              <label className="field">
                <span>Anbieter</span>
                <select
                  value={provider}
                  onChange={(event) => changeProvider(event.target.value)}
                  disabled={catalog === null}
                >
                  {Object.keys(catalog?.providers ?? {}).map((key) => (
                    <option value={key} key={key}>{providerLabel(key)}</option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Modell</span>
                <select
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  disabled={catalog === null}
                >
                  <option value={MODEL_AUTO}>Vorgabe des Anbieters</option>
                  {models.map((name) => (
                    <option value={name} key={name}>{name}</option>
                  ))}
                </select>
              </label>

              <label className="field wide">
                <span>Prompt <em>*</em></span>
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="Gib mir ein JSON mit dem Feld status=ok"
                  required
                />
                <small>
                  Das Modell wird angewiesen, ausschließlich JSON zu liefern — auch ohne
                  entsprechenden Hinweis im Prompt.
                </small>
              </label>
            </div>

            <div className="inline-actions">
              <button className="btn btn-primary" type="submit" disabled={running || prompt.trim() === ''}>
                <Icon name="check" size={16} />
                {running ? 'Wird gesendet…' : 'Anfrage senden'}
              </button>
            </div>
          </div>
        </form>

        <div className="card section-card">
          <div className="card-head">
            <h2>Antwort</h2>
          </div>
          {running ? (
            <div className="center"><div className="spinner" /></div>
          ) : answer === null ? (
            <div className="empty">
              <Icon name="info" size={40} />
              <p>Noch keine Anfrage gestellt.</p>
            </div>
          ) : (
            <div className="card-body">
              <pre className="code-block mono">{answer}</pre>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
