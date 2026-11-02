/* Klarnamen der Anbieter. Die Oberfläche zeigt nie den technischen Namen aus
   der Konfiguration, solange ein Klarname bekannt ist (eiserne Regel 12).
   Ein unbekannter Anbieter fällt auf seinen technischen Namen zurück, statt
   die Seite leer zu lassen. */

const PROVIDER_LABELS: Record<string, string> = {
  claude_sub: 'Claude (Abo)',
  codex_sub: 'ChatGPT (Abo)',
  gemini: 'Google Gemini',
  gemini_agy: 'Google Gemini (AGY)',
  gemini_web: 'Google Gemini (Web)',
}

/** Beschriftung eines Anbieters, ersatzweise sein technischer Name. */
export function providerLabel(key: string): string {
  return PROVIDER_LABELS[key] ?? key
}

/** Wert des Auswahlfelds für „kein Modell erzwingen“. */
export const MODEL_AUTO = 'auto'

/** Anbieter, dessen Modelle erst nach der Anmeldung bekannt sind; er hat eine eigene Option. */
export const DYNAMIC_MODEL_OPTIONS: Record<string, 'gemini_agy_model' | 'gemini_web_model'> = {
  gemini_agy: 'gemini_agy_model',
  gemini_web: 'gemini_web_model',
}

/* Werkzeugstufen der beiden Befehlszeilen. Der Nutzer liest, was die Stufe
   bewirkt, nicht den technischen Wert aus der Konfiguration (eiserne Regel 12). */

const TOOL_ACCESS_LABELS: Record<string, string> = {
  off: 'Keine Werkzeuge',
  web: 'Web-Recherche',
  full: 'Alle Werkzeuge',
}

/** Stufe, die Shell- und Dateizugriff im Container erlaubt. */
export const TOOL_ACCESS_FULL = 'full'

/** Beschriftung einer Werkzeugstufe, ersatzweise ihr technischer Wert. */
export function toolAccessLabel(level: string): string {
  return TOOL_ACCESS_LABELS[level] ?? level
}

/* Kontingente (GET /limits): Zustand eines Kontos und Name eines Zeitfensters.
   Der Nutzer liest „Aufgebraucht“ und „5 Stunden“, nie `exhausted` oder
   `five_hour` (eiserne Regel 12). */

const LIMIT_STATE_LABELS: Record<string, { text: string; tone: 'ok' | 'warn' | 'err' | 'muted' }> = {
  ok: { text: 'Bereit', tone: 'ok' },
  exhausted: { text: 'Aufgebraucht', tone: 'err' },
  restricted: { text: 'Eingeschränkt', tone: 'err' },
  login_required: { text: 'Anmeldung nötig', tone: 'warn' },
  unavailable: { text: 'Kein Zugang', tone: 'muted' },
  unknown: { text: 'Unbekannt', tone: 'muted' },
}

/** Beschriftung und Farbton der Pill zum Zustand; Unbekanntes gilt als „Unbekannt“. */
export function limitStateLabel(state: string): { text: string; tone: 'ok' | 'warn' | 'err' | 'muted' } {
  return LIMIT_STATE_LABELS[state] ?? LIMIT_STATE_LABELS.unknown
}

const WINDOW_LABELS: Record<string, string> = {
  five_hour: '5 Stunden',
  seven_day: 'Woche',
  seven_day_opus: 'Woche (Opus)',
  seven_day_sonnet: 'Woche (Sonnet)',
}

const MINUTES_PER_DAY = 24 * 60

/** Name eines Zeitfensters: bekannter Name, sonst aus der Länge, sonst neutral. */
export function limitWindowLabel(id: string, durationMinutes: number | null): string {
  const known = WINDOW_LABELS[id]
  if (known) return known
  if (durationMinutes === null || durationMinutes <= 0) return 'Zeitfenster'
  if (durationMinutes === 7 * MINUTES_PER_DAY) return 'Woche'
  if (durationMinutes % MINUTES_PER_DAY === 0) {
    const days = durationMinutes / MINUTES_PER_DAY
    return days === 1 ? '1 Tag' : `${days} Tage`
  }
  if (durationMinutes % 60 === 0) {
    const hours = durationMinutes / 60
    return hours === 1 ? '1 Stunde' : `${hours} Stunden`
  }
  return `${durationMinutes} Minuten`
}
