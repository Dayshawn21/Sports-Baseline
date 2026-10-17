import { useState } from 'react'
import { Alert, Button, Card, Input } from 'antd'

interface Props {
  onSubmit: (key: string) => void
  rejected: boolean
  retryAfter: number | null
  rateLimited: boolean
}

function notice(rejected: boolean, rateLimited: boolean, retryAfter: number | null): string | null {
  if (rateLimited) {
    return retryAfter === null
      ? 'Too many attempts. Try again in a minute.'
      : `Too many attempts. Try again in ${retryAfter} s.`
  }
  return rejected ? 'That key was not accepted.' : null
}

export default function AdminSignIn({ onSubmit, rejected, retryAfter, rateLimited }: Props) {
  const [key, setKey] = useState('')
  const message = notice(rejected, rateLimited, retryAfter)
  const canSubmit = key.trim() !== ''

  return (
    <div className="page-shell">
      <div className="page-container" style={{ maxWidth: 420, paddingTop: 48 }}>
        <Card>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 26,
            fontWeight: 800,
            letterSpacing: '0.03em',
            textTransform: 'uppercase',
            color: 'var(--text-primary)',
            margin: 0,
          }}>
            Admin sign-in
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '8px 0 20px' }}>
            Owner only. Enter the admin key to manage player data.
          </p>
          <form
            onSubmit={event => {
              event.preventDefault()
              if (canSubmit) onSubmit(key)
            }}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            <Input.Password
              value={key}
              onChange={event => setKey(event.target.value)}
              placeholder="Admin key"
              autoComplete="current-password"
              aria-label="Admin key"
              autoFocus
            />
            {message && <Alert type="error" message={message} showIcon />}
            <Button type="primary" htmlType="submit" disabled={!canSubmit}>
              Sign in
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
