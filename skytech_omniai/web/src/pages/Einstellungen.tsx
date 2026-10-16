import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ApiError, api, fieldErrorsOf } from '../api'
import { Icon } from '../components/Icon'
import { PageHeader, notifySettingsChanged } from '../components/Layout'
import { useToast } from '../components/Toast'
import { MODEL_AUTO, TOOL_ACCESS_FULL, providerLabel, toolAccessLabel } from '../provider'
import type {
  ModelsResponse,
  SecretKey,
  SettingsInput,
  SettingsOptions,
  SettingsResponse,
} from '../types'

/* Alles, was früher nur im Reiter „Konfiguration“ von Home Assistant ging.
   Der Server schreibt dieselben Optionen über den Supervisor; beide Wege
   zeigen also immer denselben Stand. Gespeichertes gilt ab der nächsten
   Anfrage, ein Neustart ist nicht nötig.

   Zugänge kommen vom Server nie zurück, nur ob einer hinterlegt ist. Ein
   leeres Feld heißt deshalb „unverändert“; entfernt wird ausdrücklich über
   den Knopf daneben. */

const TOOL_ACCESS_LEVELS = ['off', 'web', 'full']

const TOOL_ACCESS_HINTS: Record<string, string> = {
  off: 'Die KI antwortet allein aus ihrem Wissen und schlägt nichts nach.',
  web: 'Die KI darf im Web suchen und Seiten lesen — für Wetter, Nachrichten oder Preise.',
  full: 'Die KI darf zusätzlich Befehle ausführen und Dateien im Add-on lesen.',
}

/** Ein Zugangsfeld: Beschriftung, Erklärung und ob es mehrzeilig ist. */
interface SecretField {
  key: SecretKey
  label: string
  hint: string
  multiline?: boolean
}

const SECRET_FIELDS: SecretField[] = [
  {
    key: 'claude_oauth_token',
    label: 'Token des Claude-Abos',
    hint: 'Einmal auf einem Rechner mit Browser mit „claude setup-token“ erzeugen.',
  },
  {
    key: 'anthropic_api_key',
    label: 'Anthropic-Schlüssel',
    hint: 'Alternative zum Claude-Abo, wird nach Verbrauch abgerechnet.',
  },
  {
    key: 'codex_auth_json',
    label: 'Anmeldung des ChatGPT-Abos',
    hint: 'Den vollständigen Inhalt der Datei „auth.json“ einfügen, die „codex login“ anlegt.',
    multiline: true,
  },
  {
    key: 'openai_api_key',
    label: 'OpenAI-Schlüssel',
    hint: 'Alternative zum ChatGPT-Abo, wird nach Verbrauch abgerechnet.',
  },
  {
    key: 'gemini_api_key',
    label: 'Gemini-Schlüssel',
    hint: 'Aus Google AI Studio, wird nach Verbrauch abgerechnet.',
  },
]

const SAVED_PLACEHOLDER = '•••••••• (gespeichert)'

const MODEL_MISMATCH =
  'Dieses Modell gehört nicht zum gewählten Anbieter. Bitte ein passendes wählen.'

export function Einstellungen() {
  const [loaded, setLoaded] = useState<SettingsResponse | null>(null)
  const [catalog, setCatalog] = useState<ModelsResponse | null>(null)
  const [draft, setDraft] = useState<SettingsOptions | null>(null)
  const [removed, setRemoved] = useState<SecretKey[]>([])
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  const adopt = useCallback((value: SettingsResponse) => {
    setLoaded(value)
    setDraft(value.options)
    setRemoved([])
    setFieldErrors({})
    setConflict(false)
  }, [])

  const load = useCallback(
    () =>
      api
        .settings()
        .then((value) => {
          adopt(value)
          setError('')
        })
        .catch((cause: Error) => setError(cause.message)),
    [adopt],
  )

  useEffect(() => {
    void load()
    let cancelled = false
    api
      .models()
      .then((value) => {
        if (!cancelled) setCatalog(value)
      })
      .catch((cause: Error) => console.error('Modelle nicht abrufbar', cause))
    return () => {
      cancelled = true
    }
  }, [load])

  function patch(partial: Partial<SettingsOptions>) {
    setDraft((current) => (current ? { ...current, ...partial } : current))
    // Ein geändertes Feld ist nicht mehr das, das der Server bemängelt hat.
    setFieldErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(partial)) delete next[key]
      return next
    })
  }

  function changeProvider(next: string) {
    // Das Modell gehört zum Anbieter: eine stehengebliebene Auswahl passte
    // nicht mehr und würde beim Speichern zu Recht abgelehnt.
    patch({ provider: next, model: MODEL_AUTO })
  }

  function toggleRemoved(key: SecretKey) {
    setRemoved((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    )
    patch({ [key]: '' })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!draft || !loaded) return
    setSaving(true)
    setError('')
    try {
      const options: SettingsInput['options'] = { ...draft }
      for (const key of removed) options[key] = null
      const saved = await api.saveSettings({ options, stored_revision: loaded.stored_revision })
      adopt(saved)
      notifySettingsChanged()
      toast('Gespeichert. Gilt ab der nächsten Anfrage.')
    } catch (cause) {
      setFieldErrors(fieldErrorsOf(cause))
      setConflict(cause instanceof ApiError && cause.status === 409)
      setError((cause as Error).message)
      toast('Die Einstellungen wurden nicht gespeichert.', 'err')
    } finally {
      setSaving(false)
    }
  }

  const readOnly = loaded !== null && !loaded.can_save
  const locked = readOnly || saving
  const dirty =
    loaded !== null &&
    draft !== null &&
    (removed.length > 0 ||
      (Object.keys(draft) as (keyof SettingsOptions)[]).some((key) => draft[key] !== loaded.options[key]))

  const providers = Object.keys(catalog?.providers ?? {})
  const providerModels = draft ? (catalog?.providers[draft.provider]?.models ?? []) : []
  // Ein im Reiter „Konfiguration“ gesetztes Modell, das nicht zum Anbieter
  // passt, bleibt sichtbar — sonst zeigte das Auswahlfeld einen falschen Stand.
  const models =
    draft && draft.model !== MODEL_AUTO && !providerModels.includes(draft.model)
      ? [...providerModels, draft.model]
      : providerModels

  // Ein unpassendes Modell (gesetzt im Reiter „Konfiguration“, dessen
  // Auswahlfeld alle Anbieter mischt) wird gleich beim Laden markiert und
  // nicht erst, wenn das Speichern scheitert.
  const modelMismatch =
    draft !== null && catalog !== null && draft.model !== MODEL_AUTO && !providerModels.includes(draft.model)
  const errors: Record<string, string> = modelMismatch
    ? { model: MODEL_MISMATCH, ...fieldErrors }
    : fieldErrors

  const fieldClass = (key: string, wide = false) =>
    `field${wide ? ' wide' : ''}${errors[key] ? ' invalid' : ''}`

  const fieldError = (key: string) =>
    errors[key] ? <small className="field-error">{errors[key]}</small> : null

  return (
    <>
      <PageHeader title="Einstellungen" subtitle="Anbieter, Modell und Zugänge" />
      <div className="content form-content">
        {error ? <div className="alert">{error}</div> : null}

        {conflict ? (
          <div className="hint-box">
            Jemand hat die Einstellungen inzwischen geändert.{' '}
            <button type="button" onClick={() => void load()}>Gespeicherten Stand laden</button>
          </div>
        ) : null}

        {readOnly ? (
          <div className="hint-box">
            {loaded?.read_only_reason === 'ingress'
              ? 'Die Einstellungen lassen sich nur ändern, wenn diese Seite in Home Assistant über die Seitenleiste geöffnet ist.'
              : 'Das Add-on kommt gerade nicht an seine Einstellungen in Home Assistant und zeigt sie deshalb nur an. Bitte das Add-on neu starten; hilft das nicht, steht die Ursache im Protokoll des Add-ons.'}
          </div>
        ) : null}

        {draft === null || loaded === null ? (
          error ? null : <div className="center"><div className="spinner" /></div>
        ) : (
          <form onSubmit={(event) => void submit(event)}>
            <section className="card">
              <div className="card-head">
                <h2>Anbieter</h2>
                <div className="sub">Gilt für jede Anfrage, die selbst nichts anderes nennt</div>
              </div>
              <div className="card-body">
                <div className="form-grid">
                  <label className={fieldClass('provider')}>
                    <span>Anbieter</span>
                    <select
                      value={draft.provider}
                      onChange={(event) => changeProvider(event.target.value)}
                      disabled={locked || catalog === null}
                    >
                      {(providers.includes(draft.provider) ? providers : [draft.provider, ...providers]).map(
                        (key) => (
                          <option value={key} key={key}>{providerLabel(key)}</option>
                        ),
                      )}
                    </select>
                    {fieldError('provider')}
                  </label>

                  <label className={fieldClass('model')}>
                    <span>Standardmodell</span>
                    <select
                      value={draft.model}
                      onChange={(event) => patch({ model: event.target.value })}
                      disabled={locked || catalog === null}
                    >
                      <option value={MODEL_AUTO}>Vorgabe des Anbieters</option>
                      {models.map((name) => (
                        <option value={name} key={name}>{name}</option>
                      ))}
                    </select>
                    {fieldError('model')}
                  </label>

                  <label className={fieldClass('tool_access', true)}>
                    <span>Werkzeuge</span>
                    <select
                      value={draft.tool_access}
                      onChange={(event) => patch({ tool_access: event.target.value })}
                      disabled={locked}
                    >
                      {TOOL_ACCESS_LEVELS.map((level) => (
                        <option value={level} key={level}>{toolAccessLabel(level)}</option>
                      ))}
                    </select>
                    <small>
                      {TOOL_ACCESS_HINTS[draft.tool_access] ?? ''} Gilt für Claude und ChatGPT;
                      Gemini antwortet immer aus seinem Wissen.
                    </small>
                    {fieldError('tool_access')}
                  </label>
                </div>

                {draft.tool_access === TOOL_ACCESS_FULL ? (
                  <div className="hint-box">
                    Mit „Alle Werkzeuge“ kommt die KI auch an die hier hinterlegten Zugänge. Für
                    Anfragen, die etwas nachschlagen sollen, genügt „Web-Recherche“.
                  </div>
                ) : null}
              </div>
            </section>

            <section className="card section-card">
              <div className="card-head">
                <h2>Zugänge</h2>
                <div className="sub">Für den aktiven Anbieter genügt einer der passenden</div>
              </div>
              <div className="card-body">
                <div className="form-grid">
                  {SECRET_FIELDS.map((field) => {
                    const stored = loaded.secrets_set[field.key]
                    const removing = removed.includes(field.key)
                    const placeholder = stored && !removing ? SAVED_PLACEHOLDER : ''
                    return (
                      <div className={fieldClass(field.key, field.multiline)} key={field.key}>
                        <span>
                          <label htmlFor={`secret-${field.key}`}>{field.label}</label>{' '}
                          {removing ? (
                            <span className="pill warn">Wird beim Speichern entfernt</span>
                          ) : stored ? (
                            <span className="pill ok">Hinterlegt</span>
                          ) : (
                            <span className="pill muted">Kein Zugang</span>
                          )}
                        </span>
                        {field.multiline ? (
                          <textarea
                            id={`secret-${field.key}`}
                            className="mono"
                            value={draft[field.key]}
                            onChange={(event) => patch({ [field.key]: event.target.value })}
                            placeholder={placeholder}
                            disabled={locked || removing}
                            autoComplete="off"
                            spellCheck={false}
                          />
                        ) : (
                          <input
                            id={`secret-${field.key}`}
                            type="password"
                            value={draft[field.key]}
                            onChange={(event) => patch({ [field.key]: event.target.value })}
                            placeholder={placeholder}
                            disabled={locked || removing}
                            autoComplete="new-password"
                          />
                        )}
                        <small>
                          {field.hint}
                          {stored && !removing ? ' Leer lassen, um ihn zu behalten.' : ''}
                        </small>
                        {fieldError(field.key)}
                        {stored ? (
                          <div className="inline-actions">
                            <button
                              type="button"
                              className={`btn btn-sm ${removing ? 'btn-ghost' : 'btn-danger'}`}
                              onClick={() => toggleRemoved(field.key)}
                              disabled={locked}
                            >
                              <Icon name={removing ? 'refresh' : 'trash'} size={14} />
                              {removing ? 'Doch behalten' : 'Entfernen'}
                            </button>
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              </div>
            </section>

            {readOnly ? null : (
              <div className="form-footer">
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => adopt(loaded)}
                  disabled={!dirty || saving}
                >
                  Änderungen verwerfen
                </button>
                <button className="btn btn-primary" type="submit" disabled={!dirty || saving}>
                  <Icon name="check" size={16} />
                  {saving ? 'Speichern…' : 'Speichern'}
                </button>
              </div>
            )}
          </form>
        )}
      </div>
    </>
  )
}
