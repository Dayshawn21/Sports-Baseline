import { useState } from 'react'
import { type LogoSport, teamLogoUrl } from '~/utils/teamLogo'
import './team-logo.css'

interface Props {
  sport: LogoSport
  code: string
  size: number
  /** `none` leaves nothing behind when the image is missing, for rows that already print the code. */
  fallback?: 'badge' | 'none'
}

/** A team's logo at a fixed size; a missing code or a failed image shows the code badge (or nothing). */
export default function TeamLogo({ sport, code, size, fallback = 'badge' }: Props) {
  const url = teamLogoUrl(sport, code, size)
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const style = { width: size, height: size }
  if (url !== null && failedUrl !== url) {
    return <img className="team-logo" src={url} alt="" width={size} height={size} loading="lazy" decoding="async" style={style} onError={() => setFailedUrl(url)} />
  }
  if (fallback === 'none') return <span className="team-logo" style={style} aria-hidden="true" />
  return <span className="team-logo team-logo--badge" style={{ ...style, fontSize: Math.round(size * 0.29) }} aria-hidden="true">{code}</span>
}
