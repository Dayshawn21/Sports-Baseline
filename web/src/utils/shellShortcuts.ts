import type { ShellNav, SportView } from '~/utils/sportNav'

/** The parts of a keydown the shell shortcuts read, so the mapping is testable without a DOM. */
export interface ShortcutKey {
  key: string
  ctrlKey: boolean
  metaKey: boolean
  altKey: boolean
}

const VIEW_KEYS: Record<string, SportView> = { s: 'slate', p: 'props', m: 'model' }

/** One row per shortcut for the How it works list and the tab tooltips. */
export const SHELL_SHORTCUTS = [
  { keys: ['1', '2', '3', '4'], action: 'Tennis, NFL, NBA or NHL, keeping the view' },
  { keys: ['[', ']'], action: 'Previous or next sport, keeping the view' },
  { keys: ['S', 'P', 'M'], action: 'Slate, Props or Model for the current sport' },
  { keys: ['/'], action: 'Search the slate' },
  { keys: ['?'], action: 'Show these shortcuts' },
] as const

export const SHORTCUTS_HELP_KEY = '?'

export const VIEW_SHORTCUT: Record<SportView, string> = { slate: 'S', props: 'P', model: 'M' }

/**
 * Where a shell shortcut goes from the current nav, or null when the key is not one or has nowhere to go.
 * Sport keys reuse the tab paths, so they carry the view exactly as a click would. Shift is allowed
 * because some layouts need it for `[` and `]`; Ctrl, Cmd and Alt keys belong to the browser.
 */
export function shellShortcutTarget(event: ShortcutKey, nav: ShellNav): string | null {
  if (event.ctrlKey || event.metaKey || event.altKey) return null
  const key = event.key.toLowerCase()

  if (/^[1-9]$/.test(key)) {
    const sport = nav.sports[Number(key) - 1]
    // The sport and view already open: nothing to do.
    if (!sport || (sport.active && nav.views.some(view => view.active))) return null
    return sport.path
  }

  if (key === '[' || key === ']') {
    const current = nav.sports.findIndex(sport => sport.active)
    if (current === -1) return null
    const step = key === ']' ? 1 : -1
    return nav.sports[(current + step + nav.sports.length) % nav.sports.length].path
  }

  const view = VIEW_KEYS[key]
  if (!view) return null
  const target = nav.views.find(entry => entry.view === view)
  return target && !target.active ? target.path : null
}
