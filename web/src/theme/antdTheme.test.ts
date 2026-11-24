import { describe, expect, it } from 'vitest'
import { APP_ANTD_THEME, appAntdTheme } from '~/theme/antdTheme'

describe('appAntdTheme', () => {
  it('keeps the base theme when motion is allowed', () => {
    expect(appAntdTheme(false)).toBe(APP_ANTD_THEME)
  })

  it('turns Ant Design motion off for reduced motion and keeps the other tokens', () => {
    const reduced = appAntdTheme(true)
    expect(reduced.token?.motion).toBe(false)
    expect(reduced.token?.colorPrimary).toBe(APP_ANTD_THEME.token?.colorPrimary)
    expect(reduced.components).toBe(APP_ANTD_THEME.components)
    expect(APP_ANTD_THEME.token?.motion).toBeUndefined()
  })
})
