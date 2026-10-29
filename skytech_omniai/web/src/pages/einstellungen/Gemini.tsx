import { SecretField } from './SecretField'

export function Gemini() {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Google Gemini</h2>
        <div className="sub">Zugang per Schlüssel; das Abo steht unter „Google Gemini (AGY)“</div>
      </div>
      <div className="card-body">
        <div className="form-grid">
          <SecretField
            name="gemini_api_key"
            label="Gemini-Schlüssel"
            hint="Aus Google AI Studio, wird nach Verbrauch abgerechnet."
          />
        </div>
      </div>
    </section>
  )
}
