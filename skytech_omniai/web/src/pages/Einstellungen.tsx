import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Outlet, useMatch, useNavigate } from 'react-router-dom'
import { ApiError, api, fieldErrorsOf } from '../api'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/Layout'
import { useToast } from '../components/Toast'
import { MODEL_AUTO, DYNAMIC_MODEL_OPTIONS } from '../provider'
import { DEFAULT_SECTION, SETTINGS_SECTIONS, sectionsWithErrors } from '../settingsSections'
import type {
  ModelsResponse,
  SecretKey,
  SettingsInput,
  SettingsOptions,
  SettingsResponse,
} from '../types'
import type { SettingsForm } from './einstellungen/form'

/* Alles, was früher nur im Reiter „Konfiguration“ von Home Assistant ging.
   Der Server schreibt dieselben Optionen über den Supervisor; beide Wege
   zeigen also immer denselben Stand. Gespeichertes gilt ab der nächsten
   Anfrage, ein Neustart ist nicht nötig.

   Die Seite ist in Bereiche geteilt (settingsSections.ts), je einer für die
   Standardwerte und für jeden Anbieter. Diese Elternroute hält den Entwurf und
   speichert ihn; die Bereiche darunter (pages/einstellungen/) zeigen nur ihre
   Felder. Ein Wechsel zwischen den Bereichen verliert deshalb nichts, und ein
   Speichern gilt für alle. */

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
  const navigate = useNavigate()
  const current = useMatch('/einstellungen/:section')?.params.section

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

  const loadCatalog = useCallback(
    () =>
      api
        .models()
        .then(setCatalog)
        .catch((cause: Error) => console.error('Modelle nicht abrufbar', cause)),
    [],
  )

  useEffect(() => {
    void load()
    void loadCatalog()
  }, [load, loadCatalog])

  const patch = useCallback((partial: Partial<SettingsOptions>) => {
    setDraft((previous) => (previous ? { ...previous, ...partial } : previous))
    // Ein geändertes Feld ist nicht mehr das, das der Server bemängelt hat.
    setFieldErrors((previous) => {
      const next = { ...previous }
      for (const key of Object.keys(partial)) delete next[key]
      return next
    })
  }, [])

  const toggleRemoved = useCallback(
    (key: SecretKey) => {
      setRemoved((previous) =>
        previous.includes(key) ? previous.filter((item) => item !== key) : [...previous, key],
      )
      patch({ [key]: '' })
    },
    [patch],
  )

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!draft || !loaded) return
    setSaving(true)
    setError('')
    try {
      const options: SettingsInput['options'] = { ...draft }
      // Das gemeinsame Auswahlfeld kann keine Bezeichnung von Google tragen.
      if (DYNAMIC_MODEL_OPTIONS[draft.provider]) options.model = MODEL_AUTO
      for (const key of removed) options[key] = null
      const saved = await api.saveSettings({ options, stored_revision: loaded.stored_revision })
      adopt(saved)
      toast('Gespeichert. Gilt ab der nächsten Anfrage.')
    } catch (cause) {
      const errors = fieldErrorsOf(cause)
      setFieldErrors(errors)
      setConflict(cause instanceof ApiError && cause.status === 409)
      setError((cause as Error).message)
      toast('Die Einstellungen wurden nicht gespeichert.', 'err')
      // Der bemängelte Wert steht vielleicht in einem anderen Bereich als dem
      // offenen; dorthin wechseln, damit die Markierung zu sehen ist.
      const failing = sectionsWithErrors(errors)
      if (failing.length > 0 && !failing.some((section) => section.path === current)) {
        navigate(`/einstellungen/${failing[0].path}`)
      }
    } finally {
      setSaving(false)
    }
  }

  const readOnly = loaded !== null && !loaded.can_save
  const dirty =
    loaded !== null &&
    draft !== null &&
    (removed.length > 0 ||
      (Object.keys(draft) as (keyof SettingsOptions)[]).some((key) => draft[key] !== loaded.options[key]))
  const section = SETTINGS_SECTIONS.find((item) => item.path === current) ?? DEFAULT_SECTION

  const form: SettingsForm | null =
    loaded !== null && draft !== null
      ? {
          loaded,
          draft,
          catalog,
          removed,
          readOnly,
          locked: readOnly || saving,
          errors: fieldErrors,
          patch,
          toggleRemoved,
          reloadCatalog: () => void loadCatalog(),
        }
      : null

  return (
    <>
      <PageHeader title="Einstellungen" subtitle={section.subtitle} />
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

        {form === null ? (
          error ? null : <div className="center"><div className="spinner" /></div>
        ) : (
          <form onSubmit={(event) => void submit(event)}>
            <Outlet context={form} />

            {readOnly ? null : (
              <div className="form-footer">
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => loaded && adopt(loaded)}
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
