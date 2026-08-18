/* Klarnamen der Anbieter. Die Oberfläche zeigt nie den technischen Namen aus
   der Konfiguration, solange ein Klarname bekannt ist (eiserne Regel 12).
   Ein unbekannter Anbieter fällt auf seinen technischen Namen zurück, statt
   die Seite leer zu lassen. */

const PROVIDER_LABELS: Record<string, string> = {
  claude_sub: 'Claude (Abo)',
  gemini: 'Google Gemini',
}

/** Beschriftung eines Anbieters, ersatzweise sein technischer Name. */
export function providerLabel(key: string): string {
  return PROVIDER_LABELS[key] ?? key
}

/** Wert des Auswahlfelds für „kein Modell erzwingen“. */
export const MODEL_AUTO = 'auto'

/* Werkzeugstufen der Claude-CLI. Der Nutzer liest, was die Stufe bewirkt, nicht
   den technischen Wert aus der Konfiguration (eiserne Regel 12). */

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
