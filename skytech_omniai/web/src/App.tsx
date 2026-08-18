import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Anfrage } from './pages/Anfrage'
import { Dashboard } from './pages/Dashboard'
import { Modelle } from './pages/Modelle'

/* Ausschliesslich die Routentabelle: kein Zustand, kein Markup ausser der
   Auffangroute. Das Layout ist Elternroute mit <Outlet />, damit Navigation und
   Kopfzeile beim Seitenwechsel nicht neu montiert werden. */
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/anfrage" element={<Anfrage />} />
        <Route path="/modelle" element={<Modelle />} />
        <Route
          path="*"
          element={<div className="content"><div className="empty">Diese Seite gibt es nicht.</div></div>}
        />
      </Route>
    </Routes>
  )
}
