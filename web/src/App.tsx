import { lazy, Suspense, useCallback, useEffect, useState, type CSSProperties } from 'react'
import { ConfigProvider, Layout, Menu, Drawer, Button } from 'antd'
import { MenuOutlined } from '@ant-design/icons'
import { HashRouter, Link, Navigate, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { sportRoutes } from '~/routes/sportPages'
import { useIsMobile } from '~/hooks/useIsMobile'
import { appAntdTheme } from '~/theme/antdTheme'
import { usePrefersReducedMotion } from '~/hooks/usePrefersReducedMotion'
import { useAdminView } from '~/hooks/useAdmin'
import { useLastSportView } from '~/hooks/useLastSportView'
import { useShellShortcuts } from '~/hooks/useShellShortcuts'
import { useViewTransitionLocation } from '~/hooks/useViewTransitionLocation'
import { VIEW_SHORTCUT } from '~/utils/shellShortcuts'
import { phoneMenuItems, shellNav, sportViewForPath, type ShellNav } from '~/utils/sportNav'
import { DocumentTitleProvider } from '~/components/shared/DocumentTitleProvider'
import { SlateCommandProvider, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import SlateCommandField from '~/components/shared/SlateCommandField'
import MobileSportSwitcher from '~/components/shared/MobileSportSwitcher'
import ShortcutsPanel from '~/components/shared/ShortcutsPanel'
import AskLauncher from '~/components/ask/AskLauncher'
import LoadingState from '~/components/shared/LoadingState'
import NotFoundPage from '~/pages/NotFoundPage'

const HomePage = lazy(() => import('~/pages/HomePage'))
const ParlaysPage = lazy(() => import('~/pages/ParlaysPage'))
const HowItWorksPage = lazy(() => import('~/pages/HowItWorksPage'))
const ToolsPage = lazy(() => import('~/pages/ToolsPage'))
const AdminPage = lazy(() => import('~/pages/AdminPage'))

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

/** The wordmark is the home link, so the sport tabs start with the first sport. */
function Wordmark({ home }: { home: ShellNav['home'] }) {
  return (
    <Link to={home.path} className="app-wordmark" aria-label="Lineform home" aria-current={home.active ? 'page' : undefined}>
      Line<b>form</b>
    </Link>
  )
}

/** On one of its views the sport tab links to the page itself; on a game or player page it is only the current section. */
function sportCurrent(sport: ShellNav['sports'][number], nav: ShellNav): 'page' | 'true' | undefined {
  if (!sport.active) return undefined
  return nav.views.some(view => view.active) ? 'page' : 'true'
}

function ViewTabs({ nav, className = '' }: { nav: ShellNav, className?: string }) {
  if (nav.views.length === 0) return null
  return (
    <nav className={`sport-view-switch ${className}`} aria-label="Views">
      {nav.views.map(view => (
        <Link
          key={view.view}
          to={view.path}
          className={view.active ? 'is-selected' : ''}
          aria-current={view.active ? 'page' : undefined}
          aria-keyshortcuts={VIEW_SHORTCUT[view.view]}
          title={`${view.label} (${VIEW_SHORTCUT[view.view]})`}
        >
          {view.label}
        </Link>
      ))}
    </nav>
  )
}

/** The full top bar needs about 1040px with the search field open and 850px with it as a button. */
const PHONE_HEADER_MAX_WIDTH = 900
const COMPACT_SEARCH_MAX_WIDTH = 1100

interface CommandToggle {
  compact: boolean
  open: boolean
  setOpen: (open: boolean) => void
}

function TopBar({ nav, command }: { nav: ShellNav, command: CommandToggle }) {
  const headerStyle: CSSProperties = { ...HEADER_STYLE, padding: '0 clamp(20px, 3.2vw, 56px)', gap: 24 }
  if (command.compact && command.open) {
    return (
      <Header style={headerStyle}>
        <SlateCommandField mobile mobileExpanded onMobileExpandedChange={command.setOpen} />
      </Header>
    )
  }
  return (
    <Header style={headerStyle}>
      <Wordmark home={nav.home} />
      {/* Views sit beside the sports, ahead of the search, so the search showing only on slates never moves them. */}
      <div className="shell-nav-cluster">
        <nav className="shell-tabs" aria-label="Sports">
          {nav.sports.map((sport, index) => (
            <Link
              key={sport.code}
              to={sport.path}
              className={sport.active ? 'is-active' : ''}
              aria-current={sportCurrent(sport, nav)}
              aria-keyshortcuts={String(index + 1)}
              title={`${sport.label} (${index + 1})`}
            >
              {sport.label}
            </Link>
          ))}
        </nav>
        <ViewTabs nav={nav} />
      </div>
      {command.compact
        ? <SlateCommandField mobile onMobileExpandedChange={command.setOpen} />
        : <SlateCommandField />}
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
  const isMobile = useIsMobile(PHONE_HEADER_MAX_WIDTH)
  const compactSearch = useIsMobile(COMPACT_SEARCH_MAX_WIDTH)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [mobileCommandOpen, setMobileCommandOpen] = useState(false)
  const adminVisible = useAdminView()
  const lastView = useLastSportView(pathname)
  const nav = shellNav(pathname, adminVisible, lastView)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const openShortcuts = useCallback(() => setShortcutsOpen(true), [])
  useShellShortcuts(nav, shortcutsOpen, openShortcuts)
  const shortcutsPanel = <ShortcutsPanel open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
  const { scope: commandScope } = useSlateCommand()
  // Same rule as the field: a slate, or a game page that registered its week's games.
  const mobileCommandActive = mobileCommandOpen && (sportViewForPath(pathname) === 'slate' || commandScope !== null)

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
              <Wordmark home={nav.home} />
              <MobileSportSwitcher sports={nav.sports} />
              <SlateCommandField mobile onMobileExpandedChange={setMobileCommandOpen} />
              <AskLauncher sport={nav.sports.find(sport => sport.active)?.code ?? null} />
              <Button
                type="text"
                className="shell-menu-button"
                icon={<MenuOutlined style={{ color: 'var(--text-primary)', fontSize: 20 }} />}
                onClick={() => setDrawerOpen(true)}
                aria-label="Open navigation menu"
                aria-haspopup="dialog"
                aria-expanded={drawerOpen}
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
            items={phoneMenuItems(adminVisible)}
            onClick={({ key }) => {
              navigate(key)
              setDrawerOpen(false)
            }}
            style={{ borderRight: 'none' }}
          />
        </Drawer>
        {shortcutsPanel}
      </>
    )
  }

  return (
    <>
      <TopBar nav={nav} command={{ compact: compactSearch, open: mobileCommandActive, setOpen: setMobileCommandOpen }} />
      {shortcutsPanel}
    </>
  )
}

function AppRoutes() {
  const location = useViewTransitionLocation()
  return (
    <Routes location={location}>
      <Route path="/" element={<HomePage />} />
      {SPORT_ROUTES.map(({ path, element }) => <Route key={path} path={path} element={element} />)}
      <Route path="/nfl/prospects" element={<Navigate to="/nfl" replace />} />
      <Route path="/props" element={<Navigate to="/" replace />} />
      <Route path="/live-odds" element={<Navigate to="/" replace />} />
      <Route path="/bets" element={<Navigate to="/" replace />} />
      <Route path="/parlays" element={<ParlaysPage />} />
      <Route path="/tools" element={<ToolsPage />} />
      <Route path="/how-it-works" element={<HowItWorksPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default function App() {
  const reducedMotion = usePrefersReducedMotion()
  return (
    <ConfigProvider theme={appAntdTheme(reducedMotion)}>
      <HashRouter>
        <DocumentTitleProvider>
          <SlateCommandProvider>
            <Layout style={{ minHeight: '100vh' }}>
              <Nav />
              <Content style={{ background: 'transparent' }}>
                <Suspense fallback={<LoadingState />}>
                  <AppRoutes />
                </Suspense>
              </Content>
            </Layout>
          </SlateCommandProvider>
        </DocumentTitleProvider>
      </HashRouter>
    </ConfigProvider>
  )
}
