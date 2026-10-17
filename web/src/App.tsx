import { useEffect, useState, type CSSProperties } from 'react'
import { ConfigProvider, Layout, Menu, Drawer, Button } from 'antd'
import { MenuOutlined } from '@ant-design/icons'
import { HashRouter, Navigate, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import ParlaysPage from '~/pages/ParlaysPage'
import AdminPage from '~/pages/AdminPage'
import HowItWorksPage from '~/pages/HowItWorksPage'
import { sportRoutes } from '~/routes/sportPages'
import { useIsMobile } from '~/hooks/useIsMobile'
import { APP_ANTD_THEME } from '~/theme/antdTheme'
import { useAdminKey } from '~/hooks/useAdmin'
import { NAV_ITEMS, navKeyForPath, visibleNavItems } from '~/utils/sportNav'

const { Header, Content } = Layout

const SPORT_ROUTES = sportRoutes()

const HEADER_STYLE: CSSProperties = {
  position: 'sticky',
  top: 0,
  zIndex: 30,
  display: 'flex',
  alignItems: 'center',
  height: 'var(--nav-height)',
  lineHeight: 'var(--nav-height)',
  backdropFilter: 'blur(12px)',
  borderBottom: '1px solid var(--border-subtle)',
}

function Wordmark() {
  return (
    <span className="app-wordmark">
      Sport<b>App</b>
    </span>
  )
}

function Nav() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const isMobile = useIsMobile()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const selectedKey = navKeyForPath(pathname)
  const navItems = visibleNavItems(NAV_ITEMS, useAdminKey() !== null || import.meta.env.DEV)

  useEffect(() => {
    setDrawerOpen(false)
  }, [pathname])

  if (isMobile) {
    return (
      <>
        <Header style={{ ...HEADER_STYLE, justifyContent: 'space-between', padding: '0 12px', gap: 8 }}>
          <Wordmark />
          <Button
            type="text"
            icon={<MenuOutlined style={{ color: 'var(--text-primary)', fontSize: 20 }} />}
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation menu"
          />
        </Header>

        <Drawer
          title="Menu"
          placement="right"
          onClose={() => setDrawerOpen(false)}
          open={drawerOpen}
          styles={{
            header: { background: 'var(--bg-app)', color: 'var(--text-primary)', borderBottom: '1px solid var(--border-subtle)' },
            body: { background: 'var(--bg-app)', padding: 0 },
          }}
        >
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            items={navItems}
            onClick={({ key }) => {
              navigate(key)
              setDrawerOpen(false)
            }}
            style={{ borderRight: 'none' }}
          />
        </Drawer>
      </>
    )
  }

  return (
    <Header style={{ ...HEADER_STYLE, padding: '0 24px', gap: 24 }}>
      <Wordmark />
      <div className="mobile-scroll-x app-nav" style={{ flex: 1, minWidth: 0 }}>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={navItems}
          onClick={({ key }) => navigate(key)}
          style={{
            borderBottom: 'none',
            width: '100%',
            minWidth: 0,
            fontSize: 14,
          }}
        />
      </div>
    </Header>
  )
}

export default function App() {
  return (
    <ConfigProvider theme={APP_ANTD_THEME}>
      <HashRouter>
        <Layout style={{ minHeight: '100vh' }}>
          <Nav />
          <Content style={{ background: 'transparent' }}>
            <Routes>
              {SPORT_ROUTES.map(({ path, element }) => <Route key={path} path={path} element={element} />)}
              <Route path="/nfl/prospects" element={<Navigate to="/nfl" replace />} />
              <Route path="/props" element={<Navigate to="/" replace />} />
              <Route path="/live-odds" element={<Navigate to="/" replace />} />
              <Route path="/bets" element={<Navigate to="/" replace />} />
              <Route path="/parlays" element={<ParlaysPage />} />
              <Route path="/how-it-works" element={<HowItWorksPage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Routes>
          </Content>
        </Layout>
      </HashRouter>
    </ConfigProvider>
  )
}
