import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api'
import { providerLabel } from '../provider'
import { Icon } from './Icon'
import { ThemeSwitch } from './Theme'

/* App-Gerüst: Sidebar + Hauptspalte. Das Layout ist Elternroute mit <Outlet />,
   damit Navigation und Kopfzeile beim Seitenwechsel nicht neu montiert werden. */

const navClass = ({ isActive }: { isActive: boolean }) => `nav-item${isActive ? ' active' : ''}`

export function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [provider, setProvider] = useState<string | null>(null)
  const closeMobile = () => setMobileOpen(false)

  /* Ein Sammelaufruf beim Montieren füllt den Fuß der Sidebar. Scheitert er,
     bleibt dort ein Platzhalter stehen — die Navigation selbst hängt nicht
     daran und verschwindet nicht. */
  useEffect(() => {
    let cancelled = false
    api
      .status()
      .then((status) => {
        if (!cancelled) setProvider(providerLabel(status.provider))
      })
      .catch((cause: Error) => console.error('Zustand nicht abrufbar', cause))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="shell">
      {mobileOpen ? (
        <button className="sidebar-backdrop" aria-label="Navigation schließen" onClick={closeMobile} />
      ) : null}

      <aside className={`sidebar${mobileOpen ? ' open' : ''}`}>
        <div className="sidebar-brand">
          <span className="crest">AI</span>
          <div><b>Skytech OmniAI</b><span>Verwaltung</span></div>
        </div>

        <nav className="nav" onClick={closeMobile}>
          <NavLink to="/" end className={navClass}><Icon name="dashboard" /><span>Übersicht</span></NavLink>

          <div className="nav-label">Nutzung</div>
          <NavLink to="/anfrage" className={navClass}><Icon name="edit" /><span>Anfrage</span></NavLink>
          <NavLink to="/modelle" className={navClass}><Icon name="list" /><span>Modelle</span></NavLink>
        </nav>

        <div className="sidebar-foot">
          <span className="avatar"><Icon name="settings" size={15} /></span>
          <div className="who">
            <b>Aktiver Anbieter</b>
            <span>{provider ?? '–'}</span>
          </div>
        </div>
      </aside>

      <main className="main">
        <button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Navigation öffnen">
          <Icon name="menu" />
        </button>
        <Outlet />
      </main>
    </div>
  )
}

/** Klebrige Kopfzeile jeder Seite. Keine Seite baut sich eine eigene.
    Der Theme-Schalter sitzt hier und nicht in der Sidebar: die faehrt unter
    820px aus dem Bild, der Schalter muss aber auf jeder Seite erreichbar sein. */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="topbar">
      <div>
        <h1>{title}</h1>
        {subtitle ? <div className="sub">{subtitle}</div> : null}
      </div>
      <div className="spacer" />
      <ThemeSwitch />
      {actions}
    </div>
  )
}
