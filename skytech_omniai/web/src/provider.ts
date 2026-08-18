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
