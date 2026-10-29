/* Datenverträge zum Add-on. Spiegeln die Antworten aus docs/api-referenz.md
   wider — weicht der Server ab, wird hier nachgezogen, nicht mit `any` umgangen. */

/** Technischer Name eines Anbieters, so wie er in der Konfiguration steht. */
export type ProviderName = 'claude_sub' | 'codex_sub' | 'gemini' | 'gemini_agy' | 'gemini_web'

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
  /** Standardmodell von „Google Gemini (AGY)“; leer heißt: Google wählt. */
  gemini_agy_model: string
  gemini_web_model: string
  api_token: string
}

/** Schlüssel der Zugänge. Sie kommen vom Server immer leer zurück. */
export type SecretKey =
  | 'claude_oauth_token'
  | 'anthropic_api_key'
  | 'codex_auth_json'
  | 'openai_api_key'
  | 'gemini_api_key'
  | 'api_token'

/** Antwort von `GET /settings` und `PUT /settings`. */
export interface SettingsResponse {
  options: SettingsOptions
  /** Ob zu einem Zugang ein Wert hinterlegt ist — nie der Wert selbst. */
  secrets_set: Record<SecretKey, boolean>
  /** Stand, auf dem ein Entwurf beruht. Wird beim Speichern zurückgeschickt. */
  stored_revision: string
  /** Nur über Home Assistant lässt sich speichern. */
  can_save: boolean
  /** Warum nicht: kein Zugang zu den Optionen oder Aufruf am Ingress vorbei. */
  read_only_reason: 'supervisor' | 'ingress' | null
}

/** Was an `PUT /settings` geht. Zugang: `""` = unverändert, `null` = entfernen. */
export interface SettingsInput {
  options: Omit<SettingsOptions, SecretKey> & Record<SecretKey, string | null>
  stored_revision: string
}

/** Antwort von `GET /addon` (D-018): Name und HA-Konfigurationsseite des
    Add-ons. `config_path` fehlt ohne Supervisor — dann gibt es keinen Link. */
export interface AddonInfo {
  name: string
  config_path: string | null
}

/** Zustand eines Google-Kontos: bereit, Kontingent aufgebraucht, von Google eingeschränkt,
    Anmeldung abgelaufen oder nicht (mehr) angemeldet. */
export type GeminiAccountState = 'ok' | 'exhausted' | 'restricted' | 'login_expired' | 'signed_out'

/** Ein angemeldetes Google-Konto. `retry_at` gilt nur, solange es wartet. */
export interface GeminiAccount {
  id: string
  label: string
  state: GeminiAccountState
  retry_at: string | null
}

/** Antwort von `GET /auth/gemini-agy` und der Aktionen darunter: Stand der Anmeldung bei Google. */
export interface GeminiLoginStatus {
  /** Ob die Google-Befehlszeile im Add-on vorhanden ist. */
  available: boolean
  /** Mindestens ein Konto ist angemeldet. */
  signed_in: boolean
  /** Alle Konten in der Reihenfolge, in der sie an die Reihe kommen. */
  accounts: GeminiAccount[]
  /** Name des Kontos, das sich gerade anmeldet; es steht noch nicht in `accounts`. */
  pending_label: string | null
  /** `waiting` = Adresse da, Code fehlt; `checking` = Code übergeben, Google prüft. */
  state: 'idle' | 'waiting' | 'checking'
  /** Nur im Zustand `waiting` und nur über Home Assistant. */
  url: string | null
  seconds_left: number | null
  /** Grund, warum die letzte Anmeldung nicht geklappt hat, als fertiger Satz. */
  error: string | null
}

/** Konten von Gemini Web ohne Anmeldewerte. */
export interface GeminiWebStatus {
  accounts: GeminiAccount[]
  signed_in: boolean
}
