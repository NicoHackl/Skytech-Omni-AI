import { useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useMatch } from 'react-router-dom'
import { SETTINGS_SECTIONS } from '../settingsSections'
import { AddonFoot } from './AddonFoot'
import { Icon } from './Icon'
import { ThemeSwitch } from './Theme'

/* App-Gerüst: Sidebar + Hauptspalte. Das Layout ist Elternroute mit <Outlet />,
   damit Navigation und Kopfzeile beim Seitenwechsel nicht neu montiert werden. */

const navClass = ({ isActive }: { isActive: boolean }) => `nav-item${isActive ? ' active' : ''}`
const subNavClass = ({ isActive }: { isActive: boolean }) => `nav-item sub${isActive ? ' active' : ''}`

export function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const closeMobile = () => setMobileOpen(false)
  const inSettings = useMatch('/einstellungen/*') !== null

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

          <div className="nav-label">Verwaltung</div>
          {/* Obertab: führt zum ersten Bereich; die Bereiche stehen darunter, solange man in den Einstellungen ist. */}
          <Link to="/einstellungen" className={`nav-item${inSettings ? ' open' : ''}`} aria-expanded={inSettings}>
            <Icon name="settings" /><span>Einstellungen</span>
          </Link>
          {inSettings ? (
            <div className="nav-sub">
              {SETTINGS_SECTIONS.map((section) => (
                <NavLink key={section.path} to={`/einstellungen/${section.path}`} className={subNavClass}>
                  <span>{section.label}</span>
                </NavLink>
              ))}
            </div>
          ) : null}
        </nav>

        <AddonFoot />
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
