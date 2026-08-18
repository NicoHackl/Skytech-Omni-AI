import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { ThemeProvider } from './components/Theme'
import { ToastProvider } from './components/Toast'
import './styles.css'

/* Verdrahtung, keine Logik. Provider-Reihenfolge: Router aussen, dann Theme,
   dann Toast — Theme haengt an nichts und alles darunter darf es lesen. */

/* Home Assistant blendet das Add-on unter einem wechselnden Pfad ein. Der
   Server schreibt ihn beim Ausliefern in das <base>-Element; von dort holt sich
   das Routing seine Basis, damit die Adressleiste im eingebetteten Rahmen
   stimmt. Ohne Einbettung ist die Basis schlicht die Wurzel. */
const basis = new URL(document.baseURI).pathname

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={basis}>
      <ThemeProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
