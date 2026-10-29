import { SecretField } from './SecretField'

export function SkytechX() {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Skytech X</h2>
        <div className="sub">Damit Skytech X die Schnittstelle von OmniAI nutzen darf</div>
      </div>
      <div className="card-body">
        <div className="form-grid">
          <SecretField
            name="api_token"
            label="Token für Skytech X"
            hint="Mindestens 32 zufällige Zeichen. Dasselbe Token in Skytech X unter „Anbindungen“ eintragen."
          />
        </div>
      </div>
    </section>
  )
}
