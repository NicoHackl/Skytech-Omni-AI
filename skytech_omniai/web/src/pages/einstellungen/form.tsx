import { useOutletContext } from 'react-router-dom'
import type { ModelsResponse, SecretKey, SettingsOptions, SettingsResponse } from '../../types'

/* Der Entwurf der Seite „Einstellungen“, den die Elternroute hält und an die
   Bereiche darunter reicht. So bleibt eine ungespeicherte Änderung beim
   Wechsel zwischen den Bereichen erhalten, und ein einziger Knopf speichert
   alles. */

export interface SettingsForm {
  loaded: SettingsResponse
  draft: SettingsOptions
  /** Fehlt, solange die Modelle nicht abgerufen werden konnten. */
  catalog: ModelsResponse | null
  /** Zugänge, die beim Speichern entfernt werden. */
  removed: SecretKey[]
  /** Nur Anzeige: Speichern ist nicht möglich. */
  readOnly: boolean
  /** Nur Anzeige oder gerade beim Speichern. */
  locked: boolean
  /** Vom Server bemängelte Felder, je Option ein Satz. */
  errors: Record<string, string>
  patch: (partial: Partial<SettingsOptions>) => void
  toggleRemoved: (key: SecretKey) => void
  reloadCatalog: () => void
}

/** Der Entwurf, wie ihn die Elternroute hält. Nur unterhalb von `Einstellungen` aufrufen. */
export function useSettingsForm(): SettingsForm {
  return useOutletContext<SettingsForm>()
}

/** Klassen eines Formularfelds; mit Fehler rot umrandet. */
export function fieldClass(errors: Record<string, string>, key: string, wide = false): string {
  return `field${wide ? ' wide' : ''}${errors[key] ? ' invalid' : ''}`
}

/** Der Satz zum Fehler eines Feldes, falls es einen gibt. */
export function FieldError({ errors, name }: { errors: Record<string, string>; name: string }) {
  return errors[name] ? <small className="field-error">{errors[name]}</small> : null
}
