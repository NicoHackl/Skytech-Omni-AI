import {
  MODEL_AUTO,
  DYNAMIC_MODEL_OPTIONS,
  TOOL_ACCESS_FULL,
  providerLabel,
  toolAccessLabel,
} from '../../provider'
import { FieldError, fieldClass, useSettingsForm } from './form'

/* Was für jede Anfrage gilt, die selbst nichts anderes nennt: Anbieter,
   Standardmodell und Werkzeuge. Die Zugänge der einzelnen Anbieter stehen in
   deren eigenen Bereichen. */

const TOOL_ACCESS_LEVELS = ['off', 'web', 'full']

const TOOL_ACCESS_HINTS: Record<string, string> = {
  off: 'Die KI antwortet allein aus ihrem Wissen und schlägt nichts nach.',
  web: 'Die KI darf im Web suchen und Seiten lesen — für Wetter, Nachrichten oder Preise.',
  full: 'Die KI darf zusätzlich Befehle ausführen und Dateien im Add-on lesen.',
}

const MODEL_MISMATCH =
  'Dieses Modell gehört nicht zum gewählten Anbieter. Bitte ein passendes wählen.'

export function Allgemein() {
  const { draft, catalog, locked, errors: serverErrors, patch } = useSettingsForm()

  function changeModel(value: string) {
    // Dynamische Google-Zugänge haben eigene Felder; das gemeinsame bleibt „auto“.
    const key = DYNAMIC_MODEL_OPTIONS[draft.provider]
    if (key) patch({ [key]: value, model: MODEL_AUTO })
    else patch({ model: value })
  }

  function changeProvider(next: string) {
    // Das Modell gehört zum Anbieter: eine stehengebliebene Auswahl passte
    // nicht mehr und würde beim Speichern zu Recht abgelehnt.
    patch({ provider: next, model: MODEL_AUTO })
  }

  const providers = Object.keys(catalog?.providers ?? {})
  const providerModels = catalog?.providers[draft.provider]?.models ?? []
  // Bei dynamischen Google-Modellen gilt eine eigene Option; leer heißt „Google wählt“.
  const dynamicKey = DYNAMIC_MODEL_OPTIONS[draft.provider]
  const subscription = Boolean(dynamicKey)
  const modelKey = dynamicKey ?? 'model'
  const autoValue = subscription ? '' : MODEL_AUTO
  const modelValue = draft[modelKey]
  // Ein gesetztes Modell, das nicht in der Liste steht (im Reiter „Konfiguration“
  // gesetzt, oder die Liste ist gerade nicht abrufbar), bleibt sichtbar — sonst
  // zeigte das Auswahlfeld einen falschen Stand.
  const models =
    modelValue !== autoValue && !providerModels.includes(modelValue)
      ? [...providerModels, modelValue]
      : providerModels

  // Ein unpassendes Modell (gesetzt im Reiter „Konfiguration“, dessen
  // Auswahlfeld alle Anbieter mischt) wird gleich beim Laden markiert und
  // nicht erst, wenn das Speichern scheitert.
  const modelMismatch =
    !subscription &&
    catalog !== null &&
    draft.model !== MODEL_AUTO &&
    !providerModels.includes(draft.model)
  const errors = modelMismatch ? { model: MODEL_MISMATCH, ...serverErrors } : serverErrors

  return (
    <section className="card">
      <div className="card-head">
        <h2>Standard für Anfragen</h2>
        <div className="sub">Gilt für jede Anfrage, die selbst nichts anderes nennt</div>
      </div>
      <div className="card-body">
        <div className="form-grid">
          <label className={fieldClass(errors, 'provider')}>
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
            <FieldError errors={errors} name="provider" />
          </label>

          <label className={fieldClass(errors, modelKey)}>
            <span>Standardmodell</span>
            <select
              value={modelValue}
              onChange={(event) => changeModel(event.target.value)}
              disabled={locked || catalog === null}
            >
              <option value={autoValue}>Vorgabe des Anbieters</option>
              {models.map((name) => (
                <option value={name} key={name}>{name}</option>
              ))}
            </select>
            {subscription ? (
              <small>
                {models.length === 0
                  ? 'Die Modelle stehen nach der Anmeldung bei Google hier zur Auswahl.'
                  : 'Die Liste kommt von Google. Pro Anfrage kann ein anderes Modell gewählt werden.'}
              </small>
            ) : null}
            <FieldError errors={errors} name={modelKey} />
          </label>

          <label className={fieldClass(errors, 'tool_access', true)}>
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
              {TOOL_ACCESS_HINTS[draft.tool_access] ?? ''} Gilt für Claude, ChatGPT und
              Google Gemini (AGY), dort ohne Befehle: „Alle Werkzeuge“ wirkt wie
              „Web-Recherche“. Google Gemini mit Schlüssel antwortet immer aus seinem
              Wissen. Bei Google Gemini (Web) hat diese Auswahl keine Wirkung.
            </small>
            <FieldError errors={errors} name="tool_access" />
          </label>
        </div>

        {draft.tool_access === TOOL_ACCESS_FULL ? (
          <div className="hint-box">
            Mit „Alle Werkzeuge“ kommt die KI auch an die hinterlegten Zugänge. Für Anfragen, die
            etwas nachschlagen sollen, genügt „Web-Recherche“.
          </div>
        ) : null}
      </div>
    </section>
  )
}
