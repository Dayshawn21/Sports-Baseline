import type { AnswerBlock, AnswerSegment } from '~/types/ask'

const DATE = String.raw`\d{4}-\d{2}-\d{2}`

// The paths api/app/core/ask_links.py builds, and nothing else. A link the
// model writes to any other place renders as plain text.
const INTERNAL_PATHS: readonly RegExp[] = [
  /^\/$/,
  new RegExp(`^/nba(\\?date=${DATE})?$`),
  /^\/nfl(\?season=\d{4}&week=\d{1,2})?$/,
  /^\/(nba|nfl)\/game\/\d+$/,
  /^\/tennis\/match\/\d+$/,
  /^\/(nfl|tennis)\/player\/\d+$/,
  /^\/(nba|nfl|tennis)\/model$/,
  new RegExp(`^/nba/board(\\?date=${DATE})?$`),
  /^\/tennis\/board$/,
]

const LINK = /\[([^\]\n]+)\]\(([^)\s]+)\)/g
const BULLET = /^\s*[-*]\s+/

export function isInternalPath(path: string): boolean {
  return INTERNAL_PATHS.some(pattern => pattern.test(path))
}

function segments(line: string): AnswerSegment[] {
  const text = line.replace(/\*\*/g, '')
  const out: AnswerSegment[] = []
  let at = 0
  for (const match of text.matchAll(LINK)) {
    const [whole, label, path] = match
    if (match.index > at) out.push({ kind: 'text', text: text.slice(at, match.index) })
    out.push(isInternalPath(path) ? { kind: 'link', text: label, path } : { kind: 'text', text: label })
    at = match.index + whole.length
  }
  if (at < text.length) out.push({ kind: 'text', text: text.slice(at) })
  return out
}

/** An answer as paragraphs and bullet lists of text and internal links; no other markdown. */
export function answerBlocks(text: string): AnswerBlock[] {
  const blocks: AnswerBlock[] = []
  let paragraph: string[] = []
  let list: AnswerSegment[][] = []

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ kind: 'paragraph', segments: segments(paragraph.join(' ')) })
    paragraph = []
  }
  const flushList = () => {
    if (list.length) blocks.push({ kind: 'list', items: list })
    list = []
  }

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (!line) {
      flushParagraph()
      flushList()
    } else if (BULLET.test(line)) {
      flushParagraph()
      list.push(segments(line.replace(BULLET, '')))
    } else {
      flushList()
      paragraph.push(line)
    }
  }
  flushParagraph()
  flushList()
  return blocks
}
