import { useCallback, useEffect, useState } from 'react'
import { Drawer } from 'antd'
import { DownOutlined } from '@ant-design/icons'
import { Link, useLocation } from 'react-router-dom'
import { useSwipeToDismiss } from '~/hooks/useSwipeToDismiss'
import { VIEW_LABELS, sportViewForPath, type ShellSportTab } from '~/utils/sportNav'

/**
 * The phone header's sport name doubles as the sport switch. It opens a bottom sheet, in thumb reach,
 * whose rows carry the view being read, so NFL Props to NBA Props is two taps instead of a drawer scroll.
 */
export default function MobileSportSwitcher({ sports }: { sports: ShellSportTab[] }) {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [panel, setPanel] = useState<HTMLDivElement | null>(null)
  const close = useCallback(() => setOpen(false), [])
  const active = sports.find(sport => sport.active)

  useEffect(() => setOpen(false), [pathname])
  useSwipeToDismiss(panel, { direction: 'down', open, onDismiss: close })

  return (
    <>
      <button
        type="button"
        className="shell-mobile-sport"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={active ? `${active.label}, switch sport` : 'Choose a sport'}
        onClick={() => setOpen(true)}
      >
        {active?.label ?? 'Sports'}
        <DownOutlined aria-hidden className="shell-mobile-sport__chevron" />
      </button>
      <Drawer
        title="Switch sport"
        placement="bottom"
        height="auto"
        open={open}
        onClose={close}
        rootClassName="sport-sheet"
        panelRef={setPanel}
      >
        <nav aria-label="Sports">
          {sports.map(sport => {
            const view = VIEW_LABELS[sportViewForPath(sport.path) ?? 'slate']
            return (
              <Link
                key={sport.code}
                to={sport.path}
                className={`sport-sheet__row${sport.active ? ' is-active' : ''}`}
                aria-current={sport.path === pathname ? 'page' : sport.active ? 'true' : undefined}
                aria-label={`${sport.label} ${view}`}
                onClick={() => setOpen(false)}
              >
                <span className="sport-sheet__sport">{sport.label}</span>
                <span className="sport-sheet__view">{view}</span>
              </Link>
            )
          })}
        </nav>
      </Drawer>
    </>
  )
}
