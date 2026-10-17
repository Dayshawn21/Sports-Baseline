import { Alert, Button } from 'antd'

interface Props {
  error: unknown
  onRetry?: () => void
}

export default function ErrorState({ error, onRetry }: Props) {
  const message = error instanceof Error ? error.message : 'An error occurred'
  return (
    <div className="py-8 px-4">
      <Alert
        type="error"
        message="Failed to load data"
        description={message}
        action={onRetry ? <Button size="small" onClick={onRetry}>Retry</Button> : undefined}
        showIcon
      />
    </div>
  )
}
