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
