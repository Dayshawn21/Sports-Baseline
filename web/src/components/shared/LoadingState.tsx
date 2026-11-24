import { Spin } from 'antd'

interface Props {
  message?: string
}

export default function LoadingState({ message = 'Loading...' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <Spin size="large" />
      <p className="m-0 text-sm text-[var(--text-muted)]">{message}</p>
    </div>
  )
}
