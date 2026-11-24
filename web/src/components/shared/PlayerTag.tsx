import type { ReactNode } from 'react'
import type { PlayerTagTone } from '~/utils/playerPage'
import './player-tag.css'

/** An availability or roster tag. Tones change weight and contrast only: injury status is context, never a signal color. */
export function PlayerTag({ tone = 'default', className, children }: { tone?: PlayerTagTone, className?: string, children: ReactNode }) {
  const classes = ['player-tag', tone === 'default' ? null : `is-${tone}`, className].filter(Boolean).join(' ')
  return <span className={classes}>{children}</span>
}
