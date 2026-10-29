import { GoogleLogin } from '../../components/GoogleLogin'
import { useSettingsForm } from './form'

export function GeminiAbo() {
  const { readOnly, reloadCatalog } = useSettingsForm()
  return <GoogleLogin locked={readOnly} onModelsChange={reloadCatalog} />
}
