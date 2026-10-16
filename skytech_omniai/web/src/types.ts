/* Datenverträge zum Add-on. Spiegeln die Antworten aus docs/api-referenz.md
   wider — weicht der Server ab, wird hier nachgezogen, nicht mit `any` umgangen. */

/** Technischer Name eines Anbieters, so wie er in der Konfiguration steht. */
export type ProviderName = 'claude_sub' | 'codex_sub' | 'gemini'

/** Was ein Anbieter an Modellen anbietet. `default` = null heißt: er entscheidet selbst. */
export interface ProviderModels {
  models: string[]
  default: string | null
}

/** Antwort von `GET /models`. */
export interface ModelsResponse {
  active_provider: string
  providers: Record<string, ProviderModels>
}

/** Antwort von `GET /status`. Zu den Zugängen kommt nur ja/nein, nie ein Wert. */
export interface StatusResponse {
  provider: string
  version: string | null
  default_model: string | null
  /** Werkzeugstufe der Befehlszeilen: `off`, `web` oder `full`. */
  tool_access: string
  credentials: Record<string, boolean>
}

/** Was an `POST /ask` gesendet wird. */
export interface AskInput {
  prompt: string
  provider?: string
  model?: string
}

/** Die Antwort ist das JSON des Modells — der Aufbau steht vorher nicht fest. */
export type AskResponse = Record<string, unknown>

/** Die Felder der Seite „Einstellungen“ — dieselben wie im Reiter „Konfiguration“. */
export interface SettingsOptions {
  provider: string
  /** `auto` heißt: der Anbieter entscheidet. */
  model: string
  tool_access: string
  claude_oauth_token: string
  anthropic_api_key: string
  codex_auth_json: string
  openai_api_key: string
  gemini_api_key: string
}

/** Schlüssel der Zugänge. Sie kommen vom Server immer leer zurück. */
export type SecretKey =
  | 'claude_oauth_token'
  | 'anthropic_api_key'
  | 'codex_auth_json'
  | 'openai_api_key'
  | 'gemini_api_key'

/** Antwort von `GET /settings` und `PUT /settings`. */
export interface SettingsResponse {
  options: SettingsOptions
  /** Ob zu einem Zugang ein Wert hinterlegt ist — nie der Wert selbst. */
  secrets_set: Record<SecretKey, boolean>
  /** Stand, auf dem ein Entwurf beruht. Wird beim Speichern zurückgeschickt. */
  stored_revision: string
  /** Nur über Home Assistant lässt sich speichern. */
  can_save: boolean
}

/** Was an `PUT /settings` geht. Zugang: `""` = unverändert, `null` = entfernen. */
export interface SettingsInput {
  options: Omit<SettingsOptions, SecretKey> & Record<SecretKey, string | null>
  stored_revision: string
}
