import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { arrivedFromBoard } from '~/utils/playerPage'

/** A board arrival goes back one step, so the board returns on its own date and market; any other arrival gets `fallback`. */
export function BoardCrumb({ boardPath, label, fallback }: { boardPath: string, label: string, fallback: ReactNode }) {
  const navigate = useNavigate()
  const fromBoard = arrivedFromBoard(useLocation().state)
  if (!fromBoard) return fallback
  return <Link className="nfl-player-crumb" to={boardPath} onClick={event => { event.preventDefault(); navigate(-1) }}>{`← ${label}`}</Link>
}
