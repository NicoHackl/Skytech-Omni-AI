import { Icon } from '../../components/Icon'
import type { SecretKey } from '../../types'
import { FieldError, fieldClass, useSettingsForm } from './form'

/* Ein Zugangsfeld: Beschriftung, Stand („Hinterlegt“), Eingabe und Knopf zum
   Entfernen. Zugänge kommen vom Server nie zurück, nur ob einer hinterlegt
   ist. Ein leeres Feld heißt deshalb „unverändert“; entfernt wird
   ausdrücklich über den Knopf daneben. */

const SAVED_PLACEHOLDER = '•••••••• (gespeichert)'

export function SecretField({
  name,
  label,
  hint,
  multiline = false,
}: {
  name: SecretKey
  label: string
  hint: string
  multiline?: boolean
}) {
  const { loaded, draft, removed, locked, errors, patch, toggleRemoved } = useSettingsForm()
  const stored = loaded.secrets_set[name]
  const removing = removed.includes(name)
  const placeholder = stored && !removing ? SAVED_PLACEHOLDER : ''
  const id = `secret-${name}`

  return (
    <div className={fieldClass(errors, name, multiline)}>
      <span>
        <label htmlFor={id}>{label}</label>{' '}
        {removing ? (
          <span className="pill warn">Wird beim Speichern entfernt</span>
        ) : stored ? (
          <span className="pill ok">Hinterlegt</span>
        ) : (
          <span className="pill muted">Kein Zugang</span>
        )}
      </span>
      {multiline ? (
        <textarea
          id={id}
          className="mono"
          value={draft[name]}
          onChange={(event) => patch({ [name]: event.target.value })}
          placeholder={placeholder}
          disabled={locked || removing}
          autoComplete="off"
          spellCheck={false}
        />
      ) : (
        <input
          id={id}
          type="password"
          value={draft[name]}
          onChange={(event) => patch({ [name]: event.target.value })}
          placeholder={placeholder}
          disabled={locked || removing}
          autoComplete="new-password"
        />
      )}
      <small>
        {hint}
        {stored && !removing ? ' Leer lassen, um ihn zu behalten.' : ''}
      </small>
      <FieldError errors={errors} name={name} />
      {stored ? (
        <div className="inline-actions">
          <button
            type="button"
            className={`btn btn-sm ${removing ? 'btn-ghost' : 'btn-danger'}`}
            onClick={() => toggleRemoved(name)}
            disabled={locked}
          >
            <Icon name={removing ? 'refresh' : 'trash'} size={14} />
            {removing ? 'Doch behalten' : 'Entfernen'}
          </button>
        </div>
      ) : null}
    </div>
  )
}
