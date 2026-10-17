import type { ComponentType } from 'react'
import { describe, expect, it } from 'vitest'
import type { ViewPages } from '~/routes/sportPages'

const Page: ComponentType = () => null

// `tsc -b` compiles this file, so each @ts-expect-error fails the build if the rule stops holding.
describe('ViewPages', () => {
  it('requires a Props or Model page exactly when the views promise one', () => {
    const full: ViewPages<{ slate: string, props: string, model: string }> = { slate: Page, props: Page, model: Page, details: [] }
    const slateOnly: ViewPages<{ slate: string }> = { slate: Page, details: [] }
    // @ts-expect-error a promised props view needs its page
    const missingProps: ViewPages<{ slate: string, props: string }> = { slate: Page, details: [] }
    // @ts-expect-error no props view, so no props page
    const extraProps: ViewPages<{ slate: string }> = { slate: Page, props: Page, details: [] }
    // @ts-expect-error a promised model view needs its page
    const missingModel: ViewPages<{ slate: string, props: string, model: string }> = { slate: Page, props: Page, details: [] }
    expect([full, slateOnly, missingProps, extraProps, missingModel]).toHaveLength(5)
  })
})
