import { Select } from 'antd'
import { playerNameMatches } from '~/utils/propFilters'
import './player-picker.css'

interface Props {
  options: string[]
  value: string[]
  onChange: (players: string[]) => void
}

export default function PlayerPicker({ options, value, onChange }: Props) {
  return <Select className="player-picker" mode="multiple" allowClear showSearch aria-label="Choose players" placeholder="Choose players"
    value={value} onChange={onChange} maxTagCount="responsive" notFoundContent="No matching players"
    options={options.map(name => ({ value: name, label: name }))}
    filterOption={(input, option) => playerNameMatches(String(option?.value ?? ''), input)} />
}
