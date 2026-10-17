import { Spin } from 'antd'

interface Props {
  message?: string
}

export default function LoadingState({ message = 'Loading...' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <Spin size="large" />
      <p className="text-gray-500 text-sm">{message}</p>
    </div>
  )
}
