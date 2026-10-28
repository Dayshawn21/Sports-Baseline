import { describe, expect, it } from 'vitest'
import type { AskEvent } from '~/types/ask'
import { askReducer, turnAnnouncement, turnNote, type AskTurn } from '~/utils/askSession'

function play(...actions: Parameters<typeof askReducer>[1][]): AskTurn[] {
  return actions.reduce(askReducer, [] as AskTurn[])
}

const event = (e: AskEvent) => ({ type: 'event' as const, event: e })

describe('askReducer', () => {
  it('starts a running turn with nothing in it', () => {
    expect(play({ type: 'start', question: 'Who plays?' })).toEqual([
      { id: 1, question: 'Who plays?', tools: [], text: '', stop: null, error: null, status: 'running' },
    ])
  })

  it('tracks tool lines, streams text, then takes the final text', () => {
    const [turn] = play(
      { type: 'start', question: 'Who plays?' },
      event({ type: 'text', delta: 'Let me check.' }),
      event({ type: 'tool_start', name: 'get_slate', sport: 'nba' }),
      event({ type: 'tool_end', name: 'get_slate', ok: true }),
      event({ type: 'text', delta: 'Two games ' }),
      event({ type: 'text', delta: 'tonight.' }),
    )
    expect(turn.tools).toEqual([{ name: 'get_slate', label: 'Checking the NBA slate', state: 'ok' }])
    expect(turn.text).toBe('Let me check.Two games tonight.')
    expect(turn.status).toBe('running')

    const [done] = askReducer([turn], event({ type: 'done', stop: 'answered', text: 'Two games tonight.' }))
    expect(done).toMatchObject({ text: 'Two games tonight.', stop: 'answered', status: 'done' })
  })

  it('closes the most recent running call of the same tool', () => {
    const [turn] = play(
      { type: 'start', question: 'q' },
      event({ type: 'tool_start', name: 'find', sport: 'nba' }),
      event({ type: 'tool_end', name: 'find', ok: true }),
      event({ type: 'tool_start', name: 'find', sport: 'nfl' }),
      event({ type: 'tool_end', name: 'find', ok: false }),
      event({ type: 'tool_end', name: 'get_slate', ok: true }),
    )
    expect(turn.tools.map(tool => tool.state)).toEqual(['ok', 'failed'])
  })

  it('records a server error frame and a failed request', () => {
    const [frame] = play({ type: 'start', question: 'q' }, event({ type: 'error', message: 'Busy.' }))
    expect(frame).toMatchObject({ status: 'error', error: 'Busy.' })
    const [failed] = play({ type: 'start', question: 'q' }, { type: 'fail', message: 'Offline.' })
    expect(failed).toMatchObject({ status: 'error', error: 'Offline.' })
  })

  it('ignores anything that arrives after the turn has ended', () => {
    const turns = play(
      { type: 'start', question: 'q' },
      event({ type: 'done', stop: 'answered', text: 'Done.' }),
      event({ type: 'text', delta: 'late' }),
      { type: 'fail', message: 'cut off' },
      { type: 'stop' },
    )
    expect(turns[0]).toMatchObject({ text: 'Done.', status: 'done', error: null })
  })

  it('stops a running turn when the next question starts', () => {
    const turns = play({ type: 'start', question: 'first' }, { type: 'start', question: 'second' })
    expect(turns.map(turn => [turn.id, turn.status])).toEqual([[1, 'stopped'], [2, 'running']])
  })
})

describe('turnNote', () => {
  const finished = (stop: AskTurn['stop']) =>
    play({ type: 'start', question: 'q' }, event({ type: 'done', stop: stop ?? 'answered', text: 'a' }))[0]

  it('explains a cut-short answer and a stopped one', () => {
    expect(turnNote(finished('truncated'))).toMatch(/length limit/)
    expect(turnNote(finished('iteration_limit'))).toMatch(/may be incomplete/)
    expect(turnNote(play({ type: 'start', question: 'q' }, { type: 'stop' })[0])).toBe('Stopped.')
  })

  it('adds nothing to a complete answer, a refusal, a running turn or an error', () => {
    expect(turnNote(finished('answered'))).toBeNull()
    expect(turnNote(finished('refused'))).toBeNull()
    expect(turnNote(play({ type: 'start', question: 'q' })[0])).toBeNull()
    expect(turnNote(play({ type: 'start', question: 'q' }, { type: 'fail', message: 'x' })[0])).toBeNull()
  })
})

describe('turnAnnouncement', () => {
  it('names the running tool, never the streaming text', () => {
    const [turn] = play(
      { type: 'start', question: 'q' },
      event({ type: 'text', delta: 'Let me check.' }),
      event({ type: 'tool_start', name: 'get_slate', sport: 'nba' }),
    )
    expect(turnAnnouncement(turn)).toBe('Checking the NBA slate...')
  })

  it('reads the waiting, done, error and stopped states', () => {
    expect(turnAnnouncement(undefined)).toBe('')
    expect(turnAnnouncement(play({ type: 'start', question: 'q' }, event({ type: 'text', delta: 'Two' }))[0])).toBe('Asking Lineform...')
    expect(turnAnnouncement(play({ type: 'start', question: 'q' }, event({ type: 'done', stop: 'answered', text: 'a' }))[0])).toBe('Answer ready.')
    expect(turnAnnouncement(play({ type: 'start', question: 'q' }, event({ type: 'error', message: 'Busy.' }))[0])).toBe('Busy.')
    expect(turnAnnouncement(play({ type: 'start', question: 'q' }, { type: 'stop' })[0])).toBe('Stopped.')
  })
})
