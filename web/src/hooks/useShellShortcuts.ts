import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { isEditableTarget } from '~/utils/keyboard'
import { SHORTCUTS_HELP_KEY, shellShortcutTarget } from '~/utils/shellShortcuts'
import type { ShellNav } from '~/utils/sportNav'

/**
 * Single-key sport and view switching for the whole app; see `SHELL_SHORTCUTS`.
 * `paused` is true while the shortcuts panel is open, so keys do not navigate behind it.
 */
export function useShellShortcuts(nav: ShellNav, paused: boolean, onHelp: () => void) {
  const navigate = useNavigate()

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (paused || event.defaultPrevented || event.repeat || event.isComposing || isEditableTarget(event.target)) return
      // An open drawer (Ask, the phone menu, the sport sheet) owns the keyboard until it closes.
      if (document.querySelector('.ant-drawer-open')) return
      if (event.key === SHORTCUTS_HELP_KEY && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault()
        onHelp()
        return
      }
      const target = shellShortcutTarget(event, nav)
      if (!target) return
      event.preventDefault()
      navigate(target)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [nav, navigate, paused, onHelp])
}
