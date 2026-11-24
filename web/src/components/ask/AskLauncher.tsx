import { lazy, Suspense, useRef, useState } from 'react'
import { MessageOutlined } from '@ant-design/icons'
import { useAskStatus } from '~/hooks/useAskStatus'
import type { Sport } from '~/utils/sportNav'

// The drawer, its stream parser and session state stay out of the startup bundle until someone reaches for Ask.
const loadAskDrawer = () => import('~/components/ask/AskDrawer')
const AskDrawer = lazy(loadAskDrawer)

/** The top-bar Ask button and its drawer; renders nothing while Ask Lineform is off. */
export default function AskLauncher({ sport }: { sport: Sport | null }) {
  const { data } = useAskStatus()
  const [open, setOpen] = useState(false)
  // Mounted from the first open on, so a closed drawer keeps its conversation as before.
  const [opened, setOpened] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  if (!data?.enabled) return null
  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="ask-trigger"
        onPointerEnter={() => void loadAskDrawer()}
        onFocus={() => void loadAskDrawer()}
        onClick={() => {
          setOpened(true)
          setOpen(true)
        }}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <MessageOutlined aria-hidden="true" />
        <span>Ask</span>
      </button>
      {opened && (
        <Suspense fallback={null}>
          <AskDrawer
            open={open}
            sport={sport}
            onClose={() => setOpen(false)}
            onClosed={() => triggerRef.current?.focus()}
          />
        </Suspense>
      )}
    </>
  )
}
