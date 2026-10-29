import { GoogleLogin } from '../../components/GoogleLogin'
import { useSettingsForm } from './form'

export function GeminiAgy() {
  const { readOnly, reloadCatalog } = useSettingsForm()
  return <GoogleLogin locked={readOnly} onModelsChange={reloadCatalog} />
}
