import { Modal } from 'antd'
import { Link } from 'react-router-dom'
import { SHELL_SHORTCUTS } from '~/utils/shellShortcuts'

/** The `?` cheat sheet: the same list How it works shows, one keypress away from any page. */
export default function ShortcutsPanel({ open, onClose }: { open: boolean, onClose: () => void }) {
  return (
    <Modal title="Keyboard shortcuts" open={open} onCancel={onClose} footer={null} width={460} centered destroyOnHidden>
      <dl className="shortcut-list">
        {SHELL_SHORTCUTS.map(shortcut => (
          <div key={shortcut.action} className="shortcut-list__row">
            <dt>{shortcut.keys.map(key => <kbd key={key} className="lf-kbd">{key}</kbd>)}</dt>
            <dd>{shortcut.action}</dd>
          </div>
        ))}
      </dl>
      <p className="shortcut-list__note">
        Keys pause while you type in a field or a panel is open. Also listed on <Link to="/how-it-works" onClick={onClose}>How it works</Link>.
      </p>
    </Modal>
  )
}
