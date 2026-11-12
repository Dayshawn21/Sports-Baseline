/** Text-field parsing for the /tools calculators. An empty field is quiet, never an error. */

export type Parsed<T> =
  | { state: 'empty' }
  | { state: 'ok', value: T }
  | { state: 'invalid', reason: string }

const NUMBER = /^[+-]?(\d+(\.\d*)?|\.\d+)$/

function parseNumber(text: string): Parsed<number> {
  const trimmed = text.trim()
  if (trimmed === '') return { state: 'empty' }
  if (!NUMBER.test(trimmed)) return { state: 'invalid', reason: 'Enter a number.' }
  return { state: 'ok', value: Number(trimmed) }
}

function check<T>(parsed: Parsed<T>, valid: (value: T) => boolean, reason: string): Parsed<T> {
  if (parsed.state !== 'ok') return parsed
  return valid(parsed.value) ? parsed : { state: 'invalid', reason }
}

/** Whole American odds, +100 or longer either way (`+150`, `-110`). */
export function parseAmerican(text: string): Parsed<number> {
  return check(
    parseNumber(text),
    value => Number.isInteger(value) && Math.abs(value) >= 100,
    'American odds are whole numbers of +100 or more, or -100 or less.',
  )
}

/** Decimal odds, which always exceed 1. */
export function parseDecimal(text: string): Parsed<number> {
  return check(parseNumber(text), value => value > 1, 'Decimal odds are greater than 1.')
}

/** A percent strictly between 0 and 100, returned as a 0-1 probability. A trailing `%` is allowed. */
export function parsePercent(text: string): Parsed<number> {
  const parsed = check(
    parseNumber(text.trim().replace(/%$/, '')),
    value => value > 0 && value < 100,
    'Enter a percent between 0 and 100.',
  )
  return parsed.state === 'ok' ? { state: 'ok', value: parsed.value / 100 } : parsed
}

/** A bankroll or stake amount above zero. */
export function parsePositive(text: string): Parsed<number> {
  return check(parseNumber(text), value => value > 0, 'Enter an amount above 0.')
}
