import { SecretField } from './SecretField'

export function ChatGpt() {
  return (
    <section className="card">
      <div className="card-head">
        <h2>ChatGPT</h2>
        <div className="sub">Es genügt einer der beiden Zugänge</div>
      </div>
      <div className="card-body">
        <div className="form-grid">
          <SecretField
            name="codex_auth_json"
            label="Anmeldung des ChatGPT-Abos"
            hint="Den vollständigen Inhalt der Datei „auth.json“ einfügen, die „codex login“ anlegt."
            multiline
          />
          <SecretField
            name="openai_api_key"
            label="OpenAI-Schlüssel"
            hint="Alternative zum ChatGPT-Abo, wird nach Verbrauch abgerechnet."
          />
        </div>
      </div>
    </section>
  )
}
