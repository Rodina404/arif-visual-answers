import { createContext, useContext } from 'react'

export interface SourceRequest {
  page: number
  quote?: string
}

export interface AppCtx {
  docId: string | null
  openSource: (r: SourceRequest) => void
}

export const AppContext = createContext<AppCtx>({ docId: null, openSource: () => {} })

export function useApp(): AppCtx {
  return useContext(AppContext)
}
