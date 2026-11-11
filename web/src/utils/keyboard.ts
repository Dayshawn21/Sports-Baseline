/** True when a key press lands in something the user is typing into, where single-key shortcuts must not fire. */
export function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement
    && Boolean(target.closest('input, textarea, select, [contenteditable="true"], [contenteditable=""]'))
}
