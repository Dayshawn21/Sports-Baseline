import { useEffect, useId, useRef, useState, type FocusEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { CloseOutlined, SearchOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { firstSlateCommandPath, matchingSlateCommandTargets, normalizeSlateCommand, slateCommandPlaceholder } from '~/utils/slateCommand'
import { sportViewForPath } from '~/utils/sportNav'
import '~/components/shared/slate-command.css'

const KIND_LABEL = { match: 'Match', game: 'Game', team: 'Team', player: 'Player' } as const

interface Props {
  mobile?: boolean
  mobileExpanded?: boolean
  onMobileExpandedChange?: (expanded: boolean) => void
}

function resultCount(count: number): string {
  return `${count} slate result${count === 1 ? '' : 's'}`
}

/** A dead end names what the slate can find instead of only saying nothing matched. */
function noMatch(query: string, pathname: string): string {
  const hint = pathname.startsWith('/tennis') ? 'a player or tournament' : 'a team code, team name or player'
  return `No match for "${query.trim()}". Try ${hint}.`
}

function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement
    && Boolean(target.closest('input, textarea, select, [contenteditable="true"], [contenteditable=""]'))
}

export default function SlateCommandField({ mobile = false, mobileExpanded = false, onMobileExpandedChange }: Props) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { query, scope, setQuery, clearQuery } = useSlateCommand()
  const [focused, setFocused] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const listId = useId()
  // Slates own the field; a game page shows it too once it registers its week's games.
  const active = sportViewForPath(pathname) === 'slate' || scope !== null
  const normalizedQuery = normalizeSlateCommand(query)
  const targets = scope ? matchingSlateCommandTargets(scope.rows, query) : []
  const open = focused && normalizedQuery.length > 0
  const selectedIndex = targets.length > 0 ? Math.min(activeIndex, targets.length - 1) : -1

  useEffect(() => setActiveIndex(0), [normalizedQuery])

  useEffect(() => {
    if (mobile && mobileExpanded) inputRef.current?.focus()
  }, [mobile, mobileExpanded])

  useEffect(() => {
    if (!active) return
    function focusFromShortcut(event: KeyboardEvent) {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return
      if (event.defaultPrevented || event.repeat || event.isComposing || isEditableTarget(event.target)) return
      event.preventDefault()
      inputRef.current?.focus()
    }
    window.addEventListener('keydown', focusFromShortcut)
    return () => window.removeEventListener('keydown', focusFromShortcut)
  }, [active])

  if (!active) return null

  if (mobile && !mobileExpanded) {
    return (
      <button
        type="button"
        className="slate-command-mobile-trigger"
        aria-label="Search this slate"
        disabled={!scope}
        onClick={() => onMobileExpandedChange?.(true)}
      >
        <SearchOutlined aria-hidden="true" />
      </button>
    )
  }

  function openPath(path: string) {
    clearQuery()
    if (mobile) onMobileExpandedChange?.(false)
    navigate(path)
  }

  function closeMobile() {
    clearQuery()
    onMobileExpandedChange?.(false)
    requestAnimationFrame(() => {
      document.querySelector<HTMLButtonElement>('.slate-command-mobile-trigger')?.focus()
    })
  }

  function onKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      if (query) {
        event.preventDefault()
        clearQuery()
        return
      }
      if (mobile) {
        event.preventDefault()
        closeMobile()
        return
      }
    }
    if (open && targets.length > 0 && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActiveIndex(index => (index + step + targets.length) % targets.length)
      return
    }
    if (event.key === 'Enter' && normalizedQuery && scope) {
      const path = activeIndex > 0 && targets[selectedIndex]
        ? targets[selectedIndex].path
        : firstSlateCommandPath(scope.rows, query)
      if (path) {
        event.preventDefault()
        openPath(path)
      }
    }
  }

  function onBlur(event: FocusEvent<HTMLDivElement>) {
    if (!rootRef.current?.contains(event.relatedTarget as Node | null)) setFocused(false)
  }

  const command = (
    <div className={`slate-command${mobile ? ' slate-command--mobile' : ''}`} ref={rootRef} onFocus={() => setFocused(true)} onBlur={onBlur}>
      <div className={`slate-command__field${focused ? ' is-focused' : ''}`}>
        <SearchOutlined aria-hidden="true" />
        <input
          ref={inputRef}
          type="search"
          role="combobox"
          aria-label="Search this slate"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={open && selectedIndex >= 0 ? `${listId}-option-${selectedIndex}` : undefined}
          placeholder={slateCommandPlaceholder(pathname, scope !== null)}
          disabled={!scope}
          value={query}
          onChange={event => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <kbd aria-hidden="true">/</kbd>
      </div>
      {open && (
        <div className="slate-command__results">
          <div id={listId} role="listbox" aria-label="Slate search results">
            {targets.map((target, index) => (
              <button
                key={`${target.parentPath}:${target.key}`}
                id={`${listId}-option-${index}`}
                type="button"
                role="option"
                aria-selected={selectedIndex === index}
                className={`slate-command__result${selectedIndex === index ? ' is-active' : ''}`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => openPath(target.path)}
              >
                <span className="slate-command__kind">{KIND_LABEL[target.kind]}</span>
                <span className="slate-command__label">{target.label}</span>
                <span className="slate-command__context">{target.context}</span>
              </button>
            ))}
          </div>
          {targets.length > 0 && (
            <div className="slate-command__status" aria-hidden="true">{resultCount(targets.length)}</div>
          )}
          {targets.length === 0 && <div className="slate-command__empty" aria-hidden="true">{noMatch(query, pathname)}</div>}
        </div>
      )}
      <div className="slate-command__live" role="status">
        {open ? targets.length > 0 ? resultCount(targets.length) : noMatch(query, pathname) : ''}
      </div>
    </div>
  )

  if (!mobile) return command
  return (
    <div className="slate-command-mobile">
      {command}
      <button type="button" className="slate-command-mobile-close" aria-label="Close slate search" onClick={closeMobile}>
        <CloseOutlined aria-hidden="true" />
      </button>
    </div>
  )
}
