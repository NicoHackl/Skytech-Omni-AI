import type { SettingsOptions } from './types'

/* Die Bereiche der Seite „Einstellungen“. Eine Tabelle für Seitenleiste,
   Kopfzeile und Routen, damit keiner der drei vom anderen abweicht.
   Die Reihenfolge ist die der Seitenleiste. */

export interface SettingsSection {
  /** Letztes Stück der Adresse unter `/einstellungen`. */
  path: string
  label: string
  /** Zeile unter dem Seitentitel. */
  subtitle: string
  /** Optionen, die der Bereich bearbeitet. Ein Fehler daran führt den Nutzer hierher. */
  fields: (keyof SettingsOptions)[]
}

export const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    path: 'allgemein',
    label: 'Allgemein',
    subtitle: 'Standardanbieter, Standardmodell und Werkzeuge',
    fields: ['provider', 'model', 'gemini_agy_model', 'gemini_web_model', 'tool_access'],
  },
  {
    path: 'claude',
    label: 'Claude',
    subtitle: 'Zugang zu Claude',
    fields: ['claude_oauth_token', 'anthropic_api_key'],
  },
  {
    path: 'chatgpt',
    label: 'ChatGPT',
    subtitle: 'Zugang zu ChatGPT',
    fields: ['codex_auth_json', 'openai_api_key'],
  },
  {
    path: 'gemini',
    label: 'Google Gemini',
    subtitle: 'Zugang zu Google Gemini per Schlüssel',
    fields: ['gemini_api_key'],
  },
  {
    path: 'gemini-agy',
    label: 'Google Gemini (AGY)',
    subtitle: 'Anmeldung der Google-Konten',
    fields: [],
  },
  {
    path: 'gemini-web',
    label: 'Google Gemini (Web)',
    subtitle: 'Google-Konten für die Gemini-Web-App',
    fields: [],
  },
  {
    path: 'skytech-x',
    label: 'Skytech X',
    subtitle: 'Zugang für Skytech X',
    fields: ['api_token'],
  },
]

/** Der Bereich, in dem die Seite startet. */
export const DEFAULT_SECTION = SETTINGS_SECTIONS[0]

/** Bereiche, in denen mindestens eines der Felder einen Fehler hat. */
export function sectionsWithErrors(errors: Record<string, string>): SettingsSection[] {
  return SETTINGS_SECTIONS.filter((section) => section.fields.some((field) => field in errors))
}
