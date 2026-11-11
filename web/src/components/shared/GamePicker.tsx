import { Select } from 'antd'
import './player-picker.css'

interface Props {
  options: Array<{ value: string, label: string }>
  value: string[]
  onChange: (games: string[]) => void
}

export default function GamePicker({ options, value, onChange }: Props) {
  return <Select className="game-picker" mode="multiple" allowClear aria-label="Choose games" placeholder="All games"
    value={value} onChange={onChange} maxTagCount="responsive" showSearch={false} options={options} />
}
