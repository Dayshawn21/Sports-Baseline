import type { ReactNode } from 'react'

/** The one line under every player page: where its data comes from and how fresh it is. */
export function PlayerFooter({ children }: { children: ReactNode }) {
  return <p className="nfl-player-note nfl-player-footer">{children}</p>
}
