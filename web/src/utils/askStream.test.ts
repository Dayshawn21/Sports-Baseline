import { describe, expect, it } from 'vitest'
import { flushSseBuffer, parseSseChunks } from '~/utils/askStream'

const frame = (event: string, data: object) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

describe('parseSseChunks', () => {
  it('reads every event the API sends, in order', () => {
    const buffer =
      frame('tool_start', { name: 'get_slate', sport: 'nba' }) +
      frame('tool_end', { name: 'get_slate', ok: true }) +
      frame('text', { delta: 'Two games\ntonight.' }) +
      frame('done', { stop: 'answered', text: 'Two games tonight.' })
    expect(parseSseChunks(buffer)).toEqual({
      events: [
        { type: 'tool_start', name: 'get_slate', sport: 'nba' },
        { type: 'tool_end', name: 'get_slate', ok: true },
        { type: 'text', delta: 'Two games\ntonight.' },
        { type: 'done', stop: 'answered', text: 'Two games tonight.' },
      ],
      rest: '',
    })
  })

  it('keeps a frame split across reads until it is complete', () => {
    const whole = frame('text', { delta: 'Lakers' }) + frame('error', { message: 'Busy.' })
    const first = parseSseChunks(whole.slice(0, 30))
    expect(first.events).toEqual([])
    const second = parseSseChunks(first.rest + whole.slice(30))
    expect(second).toEqual({
      events: [{ type: 'text', delta: 'Lakers' }, { type: 'error', message: 'Busy.' }],
      rest: '',
    })
  })

  it('reads CRLF line endings, including a pair split between reads', () => {
    const crlf = frame('text', { delta: 'hi' }).replace(/\n/g, '\r\n')
    const cut = crlf.length - 1
    const first = parseSseChunks(crlf.slice(0, cut))
    expect(first.events).toEqual([])
    expect(parseSseChunks(first.rest + crlf.slice(cut)).events).toEqual([{ type: 'text', delta: 'hi' }])
  })

  it('drops pings, unknown events and malformed frames', () => {
    const buffer =
      ': ping\n\n' +
      frame('usage', { tokens: 9 }) +
      'event: text\ndata: {not json}\n\n' +
      frame('text', { wrong: 'shape' }) +
      frame('done', { stop: 'exploded', text: '' }) +
      frame('text', { delta: 'kept' })
    expect(parseSseChunks(buffer).events).toEqual([{ type: 'text', delta: 'kept' }])
  })

  it('reads an unknown or missing sport as null', () => {
    const buffer = frame('tool_start', { name: 'find', sport: 'nhl' }) + frame('tool_start', { name: 'find' })
    expect(parseSseChunks(buffer).events).toEqual([
      { type: 'tool_start', name: 'find', sport: null },
      { type: 'tool_start', name: 'find', sport: null },
    ])
  })
})

describe('flushSseBuffer', () => {
  it('reads a final frame that ended without its blank line', () => {
    const last = frame('done', { stop: 'answered', text: 'Done.' }).trimEnd()
    const { events, rest } = parseSseChunks(frame('text', { delta: 'Done.' }) + last)
    expect(events).toEqual([{ type: 'text', delta: 'Done.' }])
    expect(flushSseBuffer(rest)).toEqual([{ type: 'done', stop: 'answered', text: 'Done.' }])
  })

  it('reads a final frame that ended with a single newline', () => {
    expect(flushSseBuffer('event: error\ndata: {"message":"Busy."}\n')).toEqual([{ type: 'error', message: 'Busy.' }])
  })

  it('finds nothing in an empty, blank or ping-only leftover', () => {
    expect(flushSseBuffer('')).toEqual([])
    expect(flushSseBuffer('\n')).toEqual([])
    expect(flushSseBuffer(': ping')).toEqual([])
  })
})
