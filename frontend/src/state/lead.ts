import { createContext, useContext } from 'react'

/** Title of the component promoted to the answer's headline (its card then skips the repeat). */
export const LeadContext = createContext<string | null>(null)

export function useLeadTitle(): string | null {
  return useContext(LeadContext)
}
