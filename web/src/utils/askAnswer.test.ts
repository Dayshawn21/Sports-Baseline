import { describe, expect, it } from 'vitest'
import { answerBlocks, isInternalPath } from '~/utils/askAnswer'

describe('isInternalPath', () => {
  it.each([
    '/',
    '/nba',
    '/nba?date=2026-10-28',
    '/nfl',
    '/nfl?season=2026&week=8',
    '/nba/game/401812345',
    '/nfl/game/123',
    '/tennis/match/88',
    '/nfl/player/7',
    '/tennis/player/42',
    '/nba/model',
    '/nfl/model',
    '/tennis/model',
    '/nba/board',
    '/nba/board?date=2026-10-28',
    '/tennis/board',
  ])('accepts %s', path => {
    expect(isInternalPath(path)).toBe(true)
  })

  it.each([
    'https://lineform.example/nba',
    'http://evil.example',
    '//evil.example/nba',
    'javascript:alert(1)',
    'nba/game/1',
    '/admin',
    '/nhl',
    '/nba/game/abc',
    '/nba/player/1',
    '/nfl/board',
    '/nba?date=tomorrow',
    '/nba/game/1?x=1',
  ])('rejects %s', path => {
    expect(isInternalPath(path)).toBe(false)
  })
})

describe('answerBlocks', () => {
  it('turns an internal markdown link into a link segment', () => {
    expect(answerBlocks('See [Jrue Holiday 1.5 threes](/nba/game/21265) tonight.')).toEqual([
      {
        kind: 'paragraph',
        segments: [
          { kind: 'text', text: 'See ' },
          { kind: 'link', text: 'Jrue Holiday 1.5 threes', path: '/nba/game/21265' },
          { kind: 'text', text: ' tonight.' },
        ],
      },
    ])
  })

  it('renders any other link as its label only', () => {
    expect(answerBlocks('[click](https://evil.example) and [x](javascript:alert) and [y](/admin)')).toEqual([
      {
        kind: 'paragraph',
        segments: [
          { kind: 'text', text: 'click' },
          { kind: 'text', text: ' and ' },
          { kind: 'text', text: 'x' },
          { kind: 'text', text: ' and ' },
          { kind: 'text', text: 'y' },
        ],
      },
    ])
  })

  it('splits paragraphs on blank lines and groups bullet lines into lists', () => {
    const text = 'Two games tonight.\nBoth on the slate.\n\n- [Lakers at Suns](/nba/game/1)\n* Celtics at Knicks\n\nNo picks.'
    expect(answerBlocks(text)).toEqual([
      { kind: 'paragraph', segments: [{ kind: 'text', text: 'Two games tonight. Both on the slate.' }] },
      {
        kind: 'list',
        items: [
          [{ kind: 'link', text: 'Lakers at Suns', path: '/nba/game/1' }],
          [{ kind: 'text', text: 'Celtics at Knicks' }],
        ],
      },
      { kind: 'paragraph', segments: [{ kind: 'text', text: 'No picks.' }] },
    ])
  })

  it('drops bold markers instead of rendering them', () => {
    expect(answerBlocks('**Reference only**, not a pick.')).toEqual([
      { kind: 'paragraph', segments: [{ kind: 'text', text: 'Reference only, not a pick.' }] },
    ])
  })

  it('returns nothing for an empty answer', () => {
    expect(answerBlocks('  \n\n ')).toEqual([])
  })
})
