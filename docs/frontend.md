# Frontend — Architektur und Muster

> Gilt für jede Web-Oberfläche des Projekts. Das **Aussehen** (Tokens, Klassen, Zustände) steht in
> [design-system.md](design-system.md), der **Inhalt der Texte** in
> [nutzertexte.md](nutzertexte.md). Beides wird hier nicht wiederholt — hier steht, wie der Code
> aufgebaut ist.

Vorbild und Referenz sind die Admin-Oberflächen von `FCR_CMS` und
`FCR-Digitale-Stadion-Zeitung`. Wer hier abweicht, begründet es in
[design-entscheidungen.md](design-entscheidungen.md) — nicht im Code.

## Stack — festgelegt

| Baustein | Wahl | Warum |
|---|---|---|
| Bibliothek | React 18 | Bekannt, stabil, kein Framework-Overhead |
| Sprache | TypeScript, `strict: true` | Fehler zur Bauzeit statt im Betrieb |
| Bündler | Vite | Schneller Dev-Server, eingebauter Proxy |
| Routing | `react-router-dom` | Einzige Laufzeit-Abhängigkeit neben React |
| Styling | eine `styles.css` | siehe [design-system.md](design-system.md) |
| Zustand | React-Bordmittel (`useState`, Context) | Oberflächen dieser Größe brauchen keinen Store |
| Datenabruf | `fetch` in einem eigenen Modul | Ein typisierter Client ist kürzer als die Konfiguration einer Library |

**Nicht** verwendet und ohne ausdrückliche Entscheidung auch nicht einzuführen: Redux, Zustand,
MobX, React Query, SWR, Axios, Formik, React Hook Form, Tailwind, MUI, shadcn, Icon-Pakete.
Jede dieser Abhängigkeiten kostet mehr Wartung, als sie in einer Oberfläche mit 5–15 Seiten spart.

Neue Laufzeit-Abhängigkeit = Design-Entscheidung, siehe
[entwicklerrichtlinien.md](entwicklerrichtlinien.md).

## Verzeichnisstruktur

```text
skytech_omniai/web/
├── index.html              # nur die Hülle: #root + Modul-Script
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── main.tsx            # Einstieg: Router + Provider + styles.css
    ├── App.tsx             # ausschliesslich die Routentabelle
    ├── styles.css          # das gesamte Design-System
    ├── api.ts              # typisierter API-Client (einziger fetch-Ort)
    ├── types.ts            # Datenverträge zum Add-on
    ├── format.ts           # Rohwert → Anzeigetext (einziger Ort dafür)
    ├── provider.ts         # Klarnamen der Anbieter, Sentinel des Modellfelds
    ├── components/         # wiederverwendbar: Layout, Theme, Toast, Icon
    └── pages/              # eine Datei je Route: Dashboard, Anfrage, Modelle
```

Regel: `pages/` kennt `components/`, nie umgekehrt. Wächst eine Seite über ~150 Zeilen, wandert
der wiederverwendbare Teil nach `components/`.

Wird der Client in mehreren Anwendungen gebraucht (Frontend **und** Server), liegt das Datenmodell
in einem gemeinsamen Ordner (`shared/`) und wird per Pfad-Alias eingebunden — siehe
[architektur.md](architektur.md).

## Einstieg und Provider

`main.tsx` verdrahtet nur; es enthält keine Logik. Reihenfolge der Provider ist verbindlich:
Router außen, dann Theme, dann Toast, dann Auth — Theme hängt an nichts und alles darunter darf es
lesen, Auth meldet Fehler über Toasts und kann deshalb nicht über dem Toast-Provider liegen.

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={basis}>   {/* Basis kommt aus <base>, siehe „Einbettung“ */}
      <ThemeProvider>        {/* Pflicht — siehe „Hell und Dunkel" */}
        <ToastProvider>
          <AuthProvider>     {/* entfällt bei Anwendungen ohne Anmeldung */}
            <App />
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
```

## Hell und Dunkel

Der Schalter ist Pflicht — eiserne Regel 11 in [`../AGENTS.md`](../AGENTS.md). Die Farbwerte dazu
stehen in [design-system.md](design-system.md), hier steht nur die Mechanik.

`components/Theme.tsx` liefert drei Dinge und **keine einzige Farbe**:

| Export | Aufgabe |
|---|---|
| `ThemeProvider` | Setzt `data-theme` am `<html>`, speichert die Wahl in `localStorage`, folgt der Systemvorgabe nur so lange, wie der Nutzer nicht selbst gewählt hat |
| `useTheme()` | `{ theme, setTheme, toggleTheme }`; wirft außerhalb des Providers einen verständlichen Fehler |
| `ThemeSwitch` | Der Knopf selbst, `.icon-btn` mit `aria-pressed` und `aria-label` |

Verbindlich daran:

- `ThemeSwitch` sitzt in `PageHeader`, nicht in der Sidebar — die fährt unter 820px aus dem Bild,
  der Schalter muss aber auf jeder Seite erreichbar bleiben.
- `index.html` trägt ein kurzes Inline-Skript im `<head>`, das `data-theme` **vor** dem ersten
  Frame setzt. Ohne das blitzt die helle Oberfläche auf, bevor React geladen ist.
- Der Provider schreibt ausschließlich das Attribut. Wer im TSX auf `theme === 'dark'` verzweigt,
  um eine Farbe zu wählen, hat das System umgangen — die Verzweigung gehört in `styles.css`.
- Ein Icon oder Bild, das nur in einem Modus lesbar ist, wird über `currentColor` gelöst, nicht
  über zwei Dateien.

## Routing

`App.tsx` enthält **nur** die Routentabelle, keinen Zustand und kein Markup außer der
Fallback-Route. Das Layout ist eine Elternroute mit `<Outlet />`, damit Sidebar und Kopfzeile beim
Seitenwechsel nicht neu montiert werden.

```tsx
<Routes>
  <Route element={<Layout />}>
    <Route path="/" element={<Dashboard />} />
    <Route path="/anfrage" element={<Anfrage />} />
    <Route path="/modelle" element={<Modelle />} />
    <Route path="*" element={<div className="content"><div className="empty">Diese Seite gibt es nicht.</div></div>} />
  </Route>
</Routes>
```

Dieses Projekt verwaltet keine Datensätze, deshalb gibt es weder Anmeldung noch das Muster
**Liste / Anlegen / Bearbeiten**. Kommt es hinzu, gilt: Liste (`/x`), Anlegen (`/x/new`),
Bearbeiten (`/x/:id`), wobei Anlegen und Bearbeiten sich eine Komponente mit
`mode: 'create' | 'edit'` teilen — zwei fast gleiche Formulare laufen garantiert auseinander.

Zugriffsschutz sind kleine Wrapper-Komponenten (`Protected`, `AdminOnly`), die auf `<Navigate>`
umleiten. Der Server prüft trotzdem eigenständig; die Frontend-Prüfung ist Bequemlichkeit, keine
Sicherheit — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## API-Client

Genau **ein** Modul ruft `fetch` auf. Keine Seite und keine Komponente ruft direkt `fetch` — sonst
liegen Basis-Pfad, Header, Token und Fehlerbehandlung verstreut im Code.

Aufbau:

```ts
export class ApiError extends Error {
  constructor(message: string, public status: number, public details?: unknown) { super(message) }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  // Token, falls vorhanden: headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(new URL(path, document.baseURI), { ...options, headers })
  } catch (err) {
    // „Failed to fetch“ ist englisch und technisch — Ursache ins Log, Satz nach oben.
    console.error('Netzwerkfehler', path, err)
    throw new ApiError('Der Server ist gerade nicht erreichbar. Bitte später erneut versuchen.', 0)
  }
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await response.json() : await response.text()
  if (!response.ok) {
    // Das Add-on liefert unter „error“ bereits einen fertigen deutschen Satz.
    const detail = isJson ? (body as { error?: unknown }).error : body
    // Statuscode bleibt am Fehlerobjekt, nicht im Text: Regel 12.
    const message = typeof detail === 'string' ? detail : 'Die Anfrage hat nicht geklappt. Bitte erneut versuchen.'
    throw new ApiError(message, response.status, detail)
  }
  return body as T
}

export const api = {
  status: () => request<StatusResponse>('status'),
  models: () => request<ModelsResponse>('models'),
  ask: (data: AskInput) => request<AskResponse>('ask', { method: 'POST', body: JSON.stringify(data) }),
}
```

Verbindlich daran:

- **Die Pfade tragen kein `/api`-Präfix und keinen führenden Schrägstrich.** Sie werden gegen
  `document.baseURI` aufgelöst, weil Home Assistant das Add-on unter einem wechselnden Pfad
  einblendet — Einzelheiten unter „Einbettung“, Begründung in D-009 und D-010.
- `Content-Type` wird bei `FormData` **nicht** gesetzt — sonst fehlt die Multipart-Boundary und der
  Upload schlägt fehl.
- Jeder Aufruf ist ein benannter Eintrag im `api`-Objekt, kein roher Pfad in der Seite.
- Rückgabetypen kommen aus `types.ts` und spiegeln den Vertrag aus
  [api-referenz.md](api-referenz.md).
- Fehlertexte sind deutsch, benennen die Ursache aus Nutzersicht und enthalten **keinen
  Statuscode und keinen Klassennamen** (eiserne Regel 12). `ApiError` trägt `status` und `details`
  weiterhin — für die Zuordnung von Feldfehlern und fürs Log, nicht für den Bildschirm.
- Ein fehlgeschlagener `fetch` (kein Netz, Server aus) wird abgefangen und übersetzt. Der
  Browsertext „Failed to fetch" ist englisch und technisch und landet nie in einem Toast.
- `401` wird zentral behandelt: Token verwerfen und ein Ereignis feuern, auf das der
  `AuthProvider` mit Abmelden reagiert. Nicht in jeder Seite einzeln.

## Anzeigewerte: `format.ts`

Kein Rohwert aus der API geht direkt ins Markup. `{row.updated_at}` rendert einen ISO-Zeitstempel
mit `T` und `Z` — genau das, was eiserne Regel 12 verbietet. Zwischen Datenvertrag und Anzeige
liegt deshalb **ein** Modul:

```ts
const ZONE = 'Europe/Berlin'
const DATE_FORMAT = new Intl.DateTimeFormat('de-DE', { timeZone: ZONE, day: '2-digit', month: '2-digit', year: 'numeric' })
const TIME_FORMAT = new Intl.DateTimeFormat('de-DE', { timeZone: ZONE, hour: '2-digit', minute: '2-digit' })

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

/** `15.08.2026, 21:03` — ohne Zonenzusatz, den liest niemand. */
export function formatDateTime(iso: string | null | undefined): string {
  const value = parse(iso)
  return value ? `${DATE_FORMAT.format(value)}, ${TIME_FORMAT.format(value)}` : '–'
}
```

Verbindlich daran:

- `formatDate`, `formatTime`, `formatDateTime`, `formatNumber` und `formatQuantity` liegen hier
  und **nur** hier. Die Namen sind englisch, die Ausgabe deutsch — eiserne Regel 2 gilt auch in
  der Oberfläche.
  Ein `toLocaleString`-Aufruf in einer Seite ist ein Fehler — er läuft irgendwann auseinander.
- `timeZone` steht in der Funktion, nicht in der Ausgabe. Kein `timeZoneName`, kein angehängtes
  „Berliner Zeit".
- Leer- und Fehlwerte werden hier abgefangen und zu `–`. `null`, `undefined`, `NaN` oder
  `Invalid Date` erreichen das Markup nicht.
- Zahlen ebenso: `Intl.NumberFormat('de-DE')` mit der Genauigkeit, die die Quelle hergibt.

## Seitenmuster: Liste

Ladezustand wird über `null` unterschieden, nicht über ein zweites `loading`-Flag — `null` heißt
„noch nicht geladen", `[]` heißt „leer".

```tsx
const [rows, setRows] = useState<Eintrag[] | null>(null)
const [busy, setBusy] = useState<number | null>(null)
const { toast } = useToast()
const load = useCallback(() => api.eintraege().then(setRows).catch((err: Error) => toast(err.message, 'err')), [toast])
useEffect(() => { void load() }, [load])
```

Für Aktionen auf einer Zeile eine gemeinsame Hilfsfunktion: Zeile sperren, ausführen, Rückmeldung,
neu laden, entsperren — auch im Fehlerfall (`finally`).

Drei Zustände, immer alle drei umgesetzt:

| Zustand | Darstellung |
|---|---|
| Laden | `<div className="center"><div className="spinner" /></div>` |
| Leer | `.empty` in einer Karte: Icon, ein erklärender Satz, Primäraktion („Erste Folie anlegen") |
| Gefüllt | Tabelle (`table.data`) bei gleichförmigen Daten, Kartenliste bei Datensätzen mit Vorschau oder Sortierung |

Ein Leerzustand ohne Weg zur ersten Aktion ist eine Sackgasse und gilt als Fehler.

## Seitenmuster: Formular

- Ein Zustandsobjekt für den Datensatz, geändert über eine `patch(partial)`-Funktion.
- `saving`-Flag sperrt den Speichern-Button und wechselt seine Beschriftung auf „Speichern…".
- Feldfehler kommen als `Record<string, string>` vom Server, landen in `fieldErrors` und färben
  gezielt das betroffene Feld (`.field.invalid` + `.field-error`). Ein globaler Toast ersetzt keine
  Feldmarkierung.
- Nach dem Speichern: Toast **und** Rücknavigation zur Liste.
- Formularaufbau folgt dem Server-Schema, wo eines existiert: Feldtyp → Widget. Zwei Quellen für
  „welche Felder hat dieser Datensatz" laufen sonst auseinander.
- Zerstörende Aktionen bestätigen mit dem Namen des Objekts:
  `window.confirm('„' + titel + '" wirklich löschen?')`.

## Rückmeldung an den Nutzer

| Mittel | Wofür |
|---|---|
| Toast (`ok` / `err`) | Ergebnis einer Aktion: gespeichert, gelöscht, fehlgeschlagen. Verschwindet nach ~4 s |
| `.alert` | Fehler, der die ganze Seite betrifft und stehen bleiben muss |
| `.field-error` | Fehler an genau einem Eingabefeld |
| `.hint-box` | Fehlende Voraussetzung plus Knopf, der sie herstellt |
| `.info-strip` | Erklärung zur Bedienung einer Liste, kein Fehler |

Der Toast-Provider stellt einen `useToast()`-Hook bereit und wirft außerhalb des Providers einen
verständlichen Fehler statt `undefined` zurückzugeben.

Hier steht nur das **Mittel**. Was darin geschrieben steht — und was gerade nicht, etwa Statuscode
oder Exception-Name — regelt [nutzertexte.md](nutzertexte.md). Ein `catch`, der `err.message`
ungeprüft in einen Toast schiebt, reicht technische Texte an den Nutzer durch.

## Layout

`components/Layout.tsx` liefert zwei Dinge:

1. `Layout` — Sidebar (Marke, Navigationsgruppen mit Zählern, Fußbereich) plus `<main>` mit
   `<Outlet />`. Unter 820px als Off-Canvas-Panel mit Hintergrund-Backdrop.
2. `PageHeader` — die klebrige Kopfzeile jeder Seite: `title`, optional `subtitle`, den
   `ThemeSwitch` und optional `actions` (die Primäraktion der Seite).

Jede Seite rendert `<PageHeader …/>` gefolgt von `<div className="content">`. Keine Seite baut sich
eine eigene Kopfzeile.

Zähler in der Navigation kommen aus einem Sammelaufruf beim Montieren des Layouts; schlägt er fehl,
verschwindet nur der Zähler, nicht die Navigation.

## Konfiguration und Auslieferung

```ts
// vite.config.ts
export default defineConfig({
  base: './',                            // relative Verweise, siehe „Einbettung“
  plugins: [react()],
  server: {
    port: 5174,                          // Port je Anwendung festlegen, nicht raten
    proxy: {                             // Dev: gleiche Herkunft wie in Produktion, kein CORS
      '/ask': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/models': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/status': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
```

- Der Build prüft erst Typen, dann bündelt er: `"build": "tsc --noEmit && vite build"`. Ein Build,
  der Typfehler durchlässt, ist wertlos.
- API-Pfade sind **relativ**, ohne führenden Schrägstrich und ohne `/api`-Präfix. Keine absolute
  Basis-URL im Code, keine `VITE_API_URL`-Variable.
- Ausgeliefert wird das Bündel vom Add-on selbst (`app.py`), nicht von einem zweiten Webserver.
  Warum: D-009 in [design-entscheidungen.md](design-entscheidungen.md), Ablauf in
  [architektur.md](architektur.md).
- `index.html` enthält `lang="de"`, `data-design` am `<html>`, das Theme-Inline-Skript,
  `viewport`, einen sprechenden `<title>`, `<meta name="theme-color">` und bei internen
  Oberflächen `<meta name="robots" content="noindex, nofollow">`.

## Einbettung in Home Assistant

Die Oberfläche läuft in aller Regel **nicht** unter `/`, sondern unter einem Pfad, den Home
Assistant je Sitzung neu vergibt (`/api/hassio_ingress/<Kennung>/`). Vier Dinge hängen daran und
gehören zusammen:

| Baustein | Was er tut |
|---|---|
| `vite.config.ts` | `base: './'` — alle Verweise im Bündel sind relativ |
| `index.html` | trägt `<base href="/" />` als Vorgabe für den direkten Aufruf über den Port |
| `app.py` | schiebt beim Ausliefern ein `<base href="…">` aus dem Kopf `X-Ingress-Path` **davor**; im HTML gewinnt das erste `<base>` |
| `main.tsx` | liest `new URL(document.baseURI).pathname` und gibt ihn dem Router als `basename` |

Daraus folgt für die Arbeit an der Oberfläche:

- **Kein absoluter Pfad im Code.** Weder in einem `fetch`, noch in einem `<img src>`, noch in einem
  `<Link to>` außerhalb des Routers. Ein führender Schrägstrich zeigt an Home Assistant vorbei.
- **Nichts aus dem Pfad ableiten.** Die Kennung darin gehört zur Sitzung und bedeutet nichts.
- Wer die Oberfläche direkt über Port 8000 aufruft, sieht dasselbe — das ist der bequemere Weg
  zum Entwickeln, ersetzt aber **nicht** die Prüfung im eingebetteten Rahmen.

## Was ein Agent vor dem ersten Commit prüft

1. `tsc --noEmit` läuft fehlerfrei — `any` ist keine Lösung, sondern eine verschobene Fehlermeldung.
2. Kein direkter `fetch` außerhalb von `api.ts`.
3. Keine Literalfarbe und kein gestaltender Inline-Style im TSX.
4. Lade-, Leer- und Fehlerzustand jeder neuen Seite sind umgesetzt.
5. Jeder Button ohne sichtbaren Text hat ein `aria-label`.
6. Die Ansicht ist bei 375px Breite bedienbar.
7. Die Designsprache war geklärt, bevor gebaut wurde — nicht geraten (eiserne Regel 10).
8. Der Theme-Schalter ist erreichbar, und **jede neue Seite wurde in beiden Modi angesehen**.
   Ein Kontrastfehler fällt nur auf, wer hinschaut.
9. Kein Rohwert im Markup: Zeitstempel, Zahlen und Leerwerte laufen durch `format.ts`, keine
   technische ID, kein Statuscode und kein Zonenzusatz ist sichtbar (eiserne Regel 12,
   Prüfliste in [nutzertexte.md](nutzertexte.md)).
