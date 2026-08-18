import type { AskInput, AskResponse, ModelsResponse, StatusResponse } from './types'

/* Einziger Ort in der Oberfläche, an dem fetch aufgerufen wird. Basis, Header
   und Fehlerbehandlung liegen damit an genau einer Stelle.

   Die Pfade sind relativ und werden gegen `document.baseURI` aufgelöst: Home
   Assistant blendet das Add-on unter einem Pfad mit Sitzungskennung ein, der
   bei jedem Aufruf ein anderer ist. Ein fester Präfix wie `/api` würde dort ins
   Leere zeigen. Das passende <base> setzt der Server beim Ausliefern der
   Seite; ohne Einbettung steht es auf der Wurzel. */

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: unknown,
  ) {
    super(message)
  }
}

const MESSAGE_UNREACHABLE =
  'Das Add-on ist gerade nicht erreichbar. Bitte später erneut versuchen.'
const MESSAGE_GENERIC = 'Das hat gerade nicht geklappt. Bitte erneut versuchen.'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  // Bei FormData KEIN Content-Type setzen — sonst fehlt die Multipart-Boundary.
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(new URL(path, document.baseURI), { ...options, headers })
  } catch (cause) {
    // Der Browser meldet hier „Failed to fetch“ — englisch, technisch und für
    // den Nutzer wertlos. Ursache ins Log, verständlicher Satz nach oben.
    console.error('Netzwerkfehler', path, cause)
    throw new ApiError(MESSAGE_UNREACHABLE, 0)
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    // Das Add-on liefert unter „error“ bereits einen fertigen deutschen Satz.
    const detail = isJson ? (body as { error?: unknown }).error : body
    const message =
      typeof detail === 'string' && detail.trim() !== '' ? detail : MESSAGE_GENERIC
    // Antwortcode und Rohantwort bleiben am Fehlerobjekt und im Log, nie im
    // Text auf dem Bildschirm (eiserne Regel 12).
    console.error('Fehlerantwort', response.status, path, detail)
    throw new ApiError(message, response.status, detail)
  }

  return body as T
}

/* Jeder Endpunkt ist ein benannter Eintrag — kein roher Pfad in einer Seite. */
export const api = {
  status: () => request<StatusResponse>('status'),
  models: () => request<ModelsResponse>('models'),
  ask: (data: AskInput) =>
    request<AskResponse>('ask', { method: 'POST', body: JSON.stringify(data) }),
}
