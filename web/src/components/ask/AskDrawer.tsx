import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Drawer } from 'antd'
import { CheckOutlined, CloseOutlined, LoadingOutlined } from '@ant-design/icons'
import AskAnswer from '~/components/ask/AskAnswer'
import { useAskSession } from '~/hooks/useAskSession'
import { useIsMobile } from '~/hooks/useIsMobile'
import { turnAnnouncement, turnNote, type AskToolLine, type AskTurn } from '~/utils/askSession'
import { askStarters } from '~/utils/askStarters'
import type { Sport } from '~/utils/sportNav'
import './ask.css'

const MAX_QUESTION = 500

function ToolLine({ tool }: { tool: AskToolLine }) {
  const icon = tool.state === 'running' ? <LoadingOutlined /> : tool.state === 'ok' ? <CheckOutlined /> : <CloseOutlined />
  return (
    <li className={`ask-tool is-${tool.state}`}>
      <span className="ask-tool__icon" aria-hidden="true">{icon}</span>
      {tool.state === 'failed' ? `${tool.label} (couldn't check)` : tool.label}
    </li>
  )
}

interface TurnProps {
  turn: AskTurn
  onNavigate: () => void
  onRetry: (() => void) | null
}

function Turn({ turn, onNavigate, onRetry }: TurnProps) {
  const note = turnNote(turn)
  const waiting = turn.status === 'running' && !turn.text && turn.tools.every(tool => tool.state !== 'running')
  return (
    <article className="ask-turn" aria-busy={turn.status === 'running'}>
      <p className="ask-turn__question">{turn.question}</p>
      {turn.tools.length > 0 && (
        <ul className="ask-tools" aria-label="What Lineform checked">
          {turn.tools.map((tool, i) => <ToolLine key={i} tool={tool} />)}
        </ul>
      )}
      {waiting && (
        <p className="ask-turn__waiting">
          <LoadingOutlined aria-hidden="true" /> Thinking
        </p>
      )}
      {turn.text && <AskAnswer text={turn.text} onNavigate={onNavigate} />}
      {note && <p className="ask-turn__note">{note}</p>}
      {turn.status === 'error' && (
        <div className="ask-turn__error">
          <p>{turn.error}</p>
          {onRetry && (
            <button type="button" className="ask-turn__retry" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      )}
    </article>
  )
}

interface AskDrawerProps {
  open: boolean
  sport: Sport | null
  onClose: () => void
  onClosed: () => void
}

export default function AskDrawer({ open, sport, onClose, onClosed }: AskDrawerProps) {
  const isMobile = useIsMobile()
  const { turns, running, send, stop } = useAskSession()
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const last = turns.at(-1)

  // Keep the newest tool line and text in view while an answer streams.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [last?.text, last?.tools.length, last?.status])

  const ask = (question: string) => {
    const trimmed = question.trim()
    if (!trimmed || running) return
    setDraft('')
    void send(trimmed)
    inputRef.current?.focus()
  }

  const close = () => {
    if (running) stop()
    onClose()
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    ask(draft)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      ask(draft)
    }
  }

  return (
    <Drawer
      open={open}
      onClose={close}
      afterOpenChange={isOpen => (isOpen ? inputRef.current?.focus() : onClosed())}
      placement="right"
      width={isMobile ? '100%' : 440}
      title="Ask Lineform"
      className="ask-drawer"
      styles={{
        header: { background: 'var(--bg-app)', color: 'var(--text-primary)', borderBottom: '1px solid var(--border-subtle)' },
        body: { background: 'var(--bg-app)', padding: 0 },
      }}
    >
      <div className="ask-drawer__body">
        <p className="ask-drawer__note">
          Answers come from Lineform's data. NBA and NFL numbers are reference only, not picks.
        </p>

        <div className="ask-drawer__turns">
          {turns.length === 0 ? (
            <div className="ask-starters">
              <p className="ask-starters__label">Try asking</p>
              {askStarters(sport).map(question => (
                <button key={question} type="button" className="ask-starter" onClick={() => ask(question)}>
                  {question}
                </button>
              ))}
            </div>
          ) : (
            turns.map(turn => (
              <Turn
                key={turn.id}
                turn={turn}
                onNavigate={close}
                onRetry={turn === last && !running && turn.retryable ? () => ask(turn.question) : null}
              />
            ))
          )}
          <div ref={endRef} />
        </div>

        <p className="ask-sr-only" aria-live="polite" role="status">{turnAnnouncement(last)}</p>

        <form className="ask-form" onSubmit={onSubmit}>
          <label htmlFor="ask-question" className="ask-sr-only">Your question</label>
          <textarea
            id="ask-question"
            ref={inputRef}
            value={draft}
            maxLength={MAX_QUESTION}
            rows={2}
            placeholder="Ask about a slate, a player or a model"
            aria-describedby="ask-question-count"
            onChange={event => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
          />
          <div className="ask-form__row">
            <span id="ask-question-count" className="ask-form__count">{draft.length}/{MAX_QUESTION}</span>
            {running ? (
              <button type="button" className="ask-form__stop" onClick={stop}>
                Stop
              </button>
            ) : (
              <button type="submit" className="ask-form__send" disabled={!draft.trim()}>
                Ask
              </button>
            )}
          </div>
        </form>
      </div>
    </Drawer>
  )
}
