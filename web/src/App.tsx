import { useEffect, useState, type CSSProperties } from 'react'
import { ConfigProvider, Layout, Menu, Drawer, Button, type MenuProps } from 'antd'
import { MenuOutlined } from '@ant-design/icons'
import { HashRouter, Link, Navigate, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import ParlaysPage from '~/pages/ParlaysPage'
import AdminPage from '~/pages/AdminPage'
import HowItWorksPage from '~/pages/HowItWorksPage'
import { sportRoutes } from '~/routes/sportPages'
import { useIsMobile } from '~/hooks/useIsMobile'
import { APP_ANTD_THEME } from '~/theme/antdTheme'
import { useAdminView } from '~/hooks/useAdmin'
import { menuSections, shellNav, sportViewForPath, type ShellNav } from '~/utils/sportNav'
import { DocumentTitleProvider } from '~/components/shared/DocumentTitleProvider'
import { SlateCommandProvider } from '~/components/shared/SlateCommandProvider'
import SlateCommandField from '~/components/shared/SlateCommandField'
import AskLauncher from '~/components/ask/AskLauncher'

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
      Line<b>form</b>
    </span>
  )
}

function ViewTabs({ nav, className = '' }: { nav: ShellNav, className?: string }) {
  if (nav.views.length === 0) return null
  return (
    <nav className={`sport-view-switch ${className}`} aria-label="Views">
      {nav.views.map(view => (
        <Link key={view.view} to={view.path} className={view.active ? 'is-selected' : ''} aria-current={view.active ? 'page' : undefined}>
          {view.label}
        </Link>
      ))}
    </nav>
  )
}

/** Each sport is a labeled group of its views; a divider sets the unlabeled section's links apart from the last sport. */
function drawerItems(adminVisible: boolean): MenuProps['items'] {
  return menuSections(adminVisible).flatMap(section => section.label
    ? [{ type: 'group' as const, key: section.label, label: section.label, children: section.items }]
    : [{ type: 'divider' as const, key: 'links-divider' }, ...section.items])
}

function TopBar({ nav }: { nav: ShellNav }) {
  return (
    <Header style={{ ...HEADER_STYLE, padding: '0 clamp(20px, 3.2vw, 56px)', gap: 24 }}>
      <Wordmark />
      <nav className="shell-tabs" aria-label="Sports">
        {nav.sports.map(sport => (
          <Link key={sport.code} to={sport.path} className={sport.active ? 'is-active' : ''} aria-current={sport.active ? 'true' : undefined}>
            {sport.label}
          </Link>
        ))}
      </nav>
      <SlateCommandField />
      <ViewTabs nav={nav} />
      <nav className="shell-tabs shell-tabs--end" aria-label="More">
        {nav.links.map(link => (
          <Link key={link.key} to={link.key} className={link.active ? 'is-active' : ''} aria-current={link.active ? 'page' : undefined}>
            {link.label}
          </Link>
        ))}
      </nav>
      <AskLauncher sport={nav.sports.find(sport => sport.active)?.code ?? null} />
    </Header>
  )
}

function Nav() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const isMobile = useIsMobile()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [mobileCommandOpen, setMobileCommandOpen] = useState(false)
  const adminVisible = useAdminView()
  const nav = shellNav(pathname, adminVisible)
  const mobileCommandActive = mobileCommandOpen && sportViewForPath(pathname) === 'slate'

  useEffect(() => {
    setDrawerOpen(false)
    setMobileCommandOpen(false)
  }, [pathname])

  if (isMobile) {
    return (
      <>
        <Header style={{ ...HEADER_STYLE, padding: '0 20px', gap: 10 }}>
          {mobileCommandActive ? (
            <SlateCommandField mobile mobileExpanded onMobileExpandedChange={setMobileCommandOpen} />
          ) : (
            <>
              <Wordmark />
              <span className="shell-mobile-sport">{nav.sports.find(sport => sport.active)?.label}</span>
              <SlateCommandField mobile onMobileExpandedChange={setMobileCommandOpen} />
              <AskLauncher sport={nav.sports.find(sport => sport.active)?.code ?? null} />
              <Button
                type="text"
                icon={<MenuOutlined style={{ color: 'var(--text-primary)', fontSize: 20 }} />}
                onClick={() => setDrawerOpen(true)}
                aria-label="Open navigation menu"
              />
            </>
          )}
        </Header>
        <ViewTabs nav={nav} className="shell-views-row" />

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
            selectedKeys={[pathname]}
            items={drawerItems(adminVisible)}
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

  return <TopBar nav={nav} />
}

export default function App() {
  return (
    <ConfigProvider theme={APP_ANTD_THEME}>
      <HashRouter>
        <DocumentTitleProvider>
          <SlateCommandProvider>
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
          </SlateCommandProvider>
        </DocumentTitleProvider>
      </HashRouter>
    </ConfigProvider>
  )
}
