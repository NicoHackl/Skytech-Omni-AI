/* Einziger Ort, an dem aus einem Rohwert ein Anzeigetext wird. Kein Wert aus der
   Schnittstelle geht ungefiltert ins Markup: ein ISO-Zeitstempel, ein `null`
   oder ein NaN auf dem Bildschirm ist ein Fehler (eiserne Regel 12 in
   AGENTS.md). Die Zeitzone steht hier in der Funktion — nie als Zusatz in der
   Ausgabe. */

const ZONE = 'Europe/Berlin'
/** Was angezeigt wird, wenn kein Wert da ist. Nie "null", "N/A" oder "-1". */
const EMPTY = '–'

const DATE_FORMAT = new Intl.DateTimeFormat('de-DE', {
  timeZone: ZONE, day: '2-digit', month: '2-digit', year: 'numeric',
})
const TIME_FORMAT = new Intl.DateTimeFormat('de-DE', {
  timeZone: ZONE, hour: '2-digit', minute: '2-digit',
})

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

/** `15.08.2026` */
export function formatDate(iso: string | null | undefined): string {
  const value = parse(iso)
  return value ? DATE_FORMAT.format(value) : EMPTY
}

/** `21:03` — ohne Zonenkürzel, das interessiert niemanden. */
export function formatTime(iso: string | null | undefined): string {
  const value = parse(iso)
  return value ? TIME_FORMAT.format(value) : EMPTY
}

/** `15.08.2026, 21:03` */
export function formatDateTime(iso: string | null | undefined): string {
  const value = parse(iso)
  return value ? `${DATE_FORMAT.format(value)}, ${TIME_FORMAT.format(value)}` : EMPTY
}

/** Deutsche Schreibweise, mit der Genauigkeit der Quelle — nicht mehr. */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return EMPTY
  return new Intl.NumberFormat('de-DE', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/** Zahl mit Einheit: `30 s`, `21,5 °C`. Einheit gehört an den Wert, nicht ins Label. */
export function formatQuantity(
  value: number | null | undefined,
  unit: string,
  decimals = 0,
): string {
  const text = formatNumber(value, decimals)
  return text === EMPTY ? EMPTY : `${text} ${unit}`
}
