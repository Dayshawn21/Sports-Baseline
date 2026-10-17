import { theme, type ThemeConfig } from 'antd'

// Mirrors the :root tokens in index.css. Ant Design derives hover, active and
// border shades from these seeds, so they must be literal colors, not var().
// colorPrimary is neutral on purpose: green is reserved for positive signals,
// and Ant Design paints buttons, focus rings and selections with the primary.
export const APP_ANTD_THEME: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorBgBase: '#000000',
    colorBgContainer: '#0d0d0f',
    colorBgElevated: '#1a1a1e',
    colorBorder: 'rgba(255,255,255,0.1)',
    colorPrimary: '#f5f5f7',
    colorText: '#f5f5f7',
    colorTextPlaceholder: '#85858f',
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontFamilyCode: "'JetBrains Mono', 'Fira Mono', monospace",
    borderRadius: 8,
  },
  components: {
    Button: {
      primaryColor: '#000000',
    },
    Layout: {
      headerBg: 'rgba(0,0,0,0.85)',
      headerHeight: 56,
      bodyBg: '#000000',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkPopupBg: '#1a1a1e',
      darkItemColor: '#9a9aa3',
      darkItemHoverColor: '#f5f5f7',
      darkItemHoverBg: 'transparent',
      darkItemSelectedBg: 'transparent',
      darkItemSelectedColor: '#f5f5f7',
    },
  },
}
