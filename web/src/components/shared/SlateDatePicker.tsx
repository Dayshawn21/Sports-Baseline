import { DatePicker } from 'antd'
import dayjs from 'dayjs'

interface Props {
  /** YYYY-MM-DD, or null for a view with no single date (tennis's today and tomorrow). */
  date: string | null
  onPick: (date: string | null) => void
  placeholder?: string
  allowClear?: boolean
}

/** The page head's date picker for the day slates; it reports calendar dates, never times. */
export default function SlateDatePicker({ date, onPick, placeholder, allowClear = false }: Props) {
  return <DatePicker
    aria-label="Slate date"
    value={date ? dayjs(date) : null}
    format="ddd, MMM D"
    placeholder={placeholder}
    allowClear={allowClear}
    inputReadOnly
    onChange={value => onPick(value ? value.format('YYYY-MM-DD') : null)}
  />
}
