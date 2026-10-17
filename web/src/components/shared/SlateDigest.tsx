import type { ReactNode } from 'react'
import './slate-digest.css'

interface Props {
  label: string
  labelId: string
  /** Boxes carrying `.slate-digest__play`; each sport's box owns its signal rule. */
  children: ReactNode
}

/** The slate's plays digest (38b, shared since 38c1): the only boxed strip on a slate page. */
export function SlateDigest({ label, labelId, children }: Props) {
  return <section className="slate-digest" aria-labelledby={labelId}>
    <h2 id={labelId} className="slate-digest__label">{label}</h2>
    <div className="slate-digest__plays">{children}</div>
  </section>
}
