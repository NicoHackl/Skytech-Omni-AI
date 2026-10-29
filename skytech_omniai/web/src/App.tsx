import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Anfrage } from './pages/Anfrage'
import { Dashboard } from './pages/Dashboard'
import { Einstellungen } from './pages/Einstellungen'
import { Modelle } from './pages/Modelle'
import { Allgemein } from './pages/einstellungen/Allgemein'
import { ChatGpt } from './pages/einstellungen/ChatGpt'
import { Claude } from './pages/einstellungen/Claude'
import { Gemini } from './pages/einstellungen/Gemini'
import { GeminiAbo } from './pages/einstellungen/GeminiAbo'
import { SkytechX } from './pages/einstellungen/SkytechX'
import { DEFAULT_SECTION } from './settingsSections'

/* Ausschliesslich die Routentabelle: kein Zustand, kein Markup ausser der
   Auffangroute. Das Layout ist Elternroute mit <Outlet />, damit Navigation und
   Kopfzeile beim Seitenwechsel nicht neu montiert werden. Die Einstellungen sind
   selbst Elternroute: ihre Bereiche teilen sich einen Entwurf (settingsSections.ts). */
export function App() {
  const settingsStart = `/einstellungen/${DEFAULT_SECTION.path}`
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/anfrage" element={<Anfrage />} />
        <Route path="/modelle" element={<Modelle />} />
        <Route path="/einstellungen" element={<Einstellungen />}>
          <Route index element={<Navigate to={settingsStart} replace />} />
          <Route path="allgemein" element={<Allgemein />} />
          <Route path="claude" element={<Claude />} />
          <Route path="chatgpt" element={<ChatGpt />} />
          <Route path="gemini" element={<Gemini />} />
          <Route path="gemini-abo" element={<GeminiAbo />} />
          <Route path="skytech-x" element={<SkytechX />} />
          <Route path="*" element={<Navigate to={settingsStart} replace />} />
        </Route>
        <Route
          path="*"
          element={<div className="content"><div className="empty">Diese Seite gibt es nicht.</div></div>}
        />
      </Route>
    </Routes>
  )
}
