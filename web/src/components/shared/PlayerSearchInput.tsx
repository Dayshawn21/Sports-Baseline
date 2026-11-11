import { SearchOutlined } from '@ant-design/icons'
import { Input } from 'antd'
import './player-search-input.css'

interface Props {
  value: string
  onChange: (value: string) => void
}

export default function PlayerSearchInput({ value, onChange }: Props) {
  return <Input className="player-search-input" aria-label="Search players" placeholder="Search players" allowClear
    prefix={<SearchOutlined aria-hidden="true" />} value={value} maxLength={64} onChange={event => onChange(event.target.value)} />
}
