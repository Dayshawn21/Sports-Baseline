/** A slate row's props count: "--" when none are stored, so an empty row does not read like a number. */
export function slatePropsText(count: number): string {
  return count === 0 ? '--' : String(count)
}
