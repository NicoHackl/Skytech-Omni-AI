import { SecretField } from './SecretField'

export function Claude() {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Claude</h2>
        <div className="sub">Es genügt einer der beiden Zugänge</div>
      </div>
      <div className="card-body">
        <div className="form-grid">
          <SecretField
            name="claude_oauth_token"
            label="Token des Claude-Abos"
            hint="Einmal auf einem Rechner mit Browser mit „claude setup-token“ erzeugen."
          />
          <SecretField
            name="anthropic_api_key"
            label="Anthropic-Schlüssel"
            hint="Alternative zum Claude-Abo, wird nach Verbrauch abgerechnet."
          />
        </div>
      </div>
    </section>
  )
}
