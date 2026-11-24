import { Menu } from 'antd'
import { phoneMenuItems } from '~/utils/sportNav'

interface PhoneMenuProps {
  pathname: string
  adminVisible: boolean
  onNavigate: (path: string) => void
}

/** The phone drawer's page list. Its own chunk, because antd's Menu is the shell's heaviest dependency. */
export default function PhoneMenu({ pathname, adminVisible, onNavigate }: PhoneMenuProps) {
  return (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[pathname]}
      items={phoneMenuItems(adminVisible)}
      onClick={({ key }) => onNavigate(key)}
      style={{ borderRight: 'none' }}
    />
  )
}
