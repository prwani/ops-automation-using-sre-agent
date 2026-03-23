import { useMsal } from '@azure/msal-react'
import { loginRequest } from './msalConfig'

export function useApiToken() {
  const { instance, accounts } = useMsal()

  const getToken = async (): Promise<string> => {
    const account = accounts[0]
    if (!account) throw new Error('No account found')
    const result = await instance.acquireTokenSilent({
      ...loginRequest,
      account,
    })
    return result.accessToken
  }

  return { getToken }
}
