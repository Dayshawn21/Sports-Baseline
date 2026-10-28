import { useRef, useState } from 'react'
import { MessageOutlined } from '@ant-design/icons'
import AskDrawer from '~/components/ask/AskDrawer'
import { useAskStatus } from '~/hooks/useAskStatus'
import type { Sport } from '~/utils/sportNav'

/** The top-bar Ask button and its drawer; renders nothing while Ask Lineform is off. */
export default function AskLauncher({ sport }: { sport: Sport | null }) {
  const { data } = useAskStatus()
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  if (!data?.enabled) return null
  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="ask-trigger"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <MessageOutlined aria-hidden="true" />
        <span>Ask</span>
      </button>
      <AskDrawer
        open={open}
        sport={sport}
        onClose={() => setOpen(false)}
        onClosed={() => triggerRef.current?.focus()}
      />
    </>
  )
}
