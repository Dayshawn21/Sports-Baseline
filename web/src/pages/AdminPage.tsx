import { useEffect, useState } from 'react'
import {
  Button,
  Table,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useQueryClient } from '@tanstack/react-query'
import type { FlaggedPlayer } from '~/types/admin'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useAdminSession, useFetchPlayerElo, useFetchPlayerStats, useFlaggedPlayers, useSetPlayerElo } from '~/hooks/useAdmin'
import { AdminActions, type AdminPanel } from '~/components/admin/AdminActions'
import { FetchEloPanel, FixStatsPanel, SetEloPanel } from '~/components/admin/AdminRepairPanels'
import AdminSignIn from '~/components/admin/AdminSignIn'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { EMPTY_ELO_INPUTS, buildSetEloPayload, fetchEloPayload, fixStatsPayload, surfaceGapNote, type SetEloInputs } from '~/utils/adminFlags'
import { sessionAdminKey } from '~/utils/adminAuth'
import { httpStatus, retryAfterSeconds } from '~/utils/httpError'
import PropsAuditBanner from '~/components/tennis/PropsAuditBanner'
import { withAlpha } from '~/utils/color'
import { tourColor } from '~/utils/format'

const FLAG_META: Record<string, { color: string; bg: string; border: string }> = {
  elo_missing:         { color: 'var(--negative)', bg: 'var(--negative-soft)',    border: 'color-mix(in srgb, var(--negative) 30%, transparent)' },
  p1_elo_missing:      { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
  p2_elo_missing:      { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
  ml_features_partial: { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
  high_overround:      { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
}

function SurfaceGapNote({ missingSurfaces }: { missingSurfaces: string[] }) {
  const note = surfaceGapNote(missingSurfaces)
  return note ? <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, maxWidth: 320 }}>{note}</div> : null
}

function FlagPill({ flag }: { flag: string }) {
  const meta = FLAG_META[flag] ?? { color: 'var(--text-secondary)', bg: 'var(--border-card)', border: 'var(--border-card)' }
  return (
    <span style={{
      fontFamily: 'var(--font-display)',
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      color: meta.color,
      background: meta.bg,
      border: `1px solid ${meta.border}`,
      borderRadius: 3,
      padding: '2px 7px',
      whiteSpace: 'nowrap',
    }}>
      {flag}
    </span>
  )
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: ok ? 'var(--positive)' : 'var(--negative)',
    }}>
      <span style={{
        width: 7,
        height: 7,
        borderRadius: '50%',
        background: ok ? 'var(--positive)' : 'var(--negative)',
        display: 'inline-block',
      }} />
      {ok ? 'Yes' : 'No'}
    </span>
  )
}

type ActivePanel = AdminPanel | null

export default function AdminPage() {
  const qc = useQueryClient()
  const session = useAdminSession()
  const [attempted, setAttempted] = useState(false)

  useEffect(() => {
    if (session.isSuccess) setAttempted(false)
  }, [session.isSuccess])

  // A cached session or flagged list must never outlive the key that loaded it.
  function signIn(key: string) {
    qc.removeQueries({ queryKey: ['admin'] })
    setAttempted(true)
    sessionAdminKey.store(key)
  }

  function signOut() {
    qc.removeQueries({ queryKey: ['admin'] })
    setAttempted(false)
    sessionAdminKey.clear()
  }

  if (session.isPending) return <LoadingState message="Checking admin access..." />
  if (session.isError) {
    const status = httpStatus(session.error)
    if (status === 401 || status === 429) {
      return (
        <AdminSignIn
          onSubmit={signIn}
          rejected={attempted}
          rateLimited={status === 429}
          retryAfter={retryAfterSeconds(session.error)}
        />
      )
    }
    return <ErrorState error={session.error} onRetry={() => session.refetch()} />
  }
  return <AdminConsole onSignOut={session.data.keyRequired ? signOut : undefined} />
}

function AdminConsole({ onSignOut }: { onSignOut?: () => void }) {
  const isMobile = useIsMobile()
  const [messageApi, contextHolder] = message.useMessage()

  // Which panel is open per player: playerId → 'stats' | 'elo' | null
  const [activePanel, setActivePanel] = useState<Record<number, ActivePanel>>({})
  // Slug input per player (for Fix Stats)
  const [slugInputs, setSlugInputs] = useState<Record<number, string>>({})
  // Name input per player (for Fetch ELO)
  const [eloNameInputs, setEloNameInputs] = useState<Record<number, string>>({})
  // Manual ELO inputs per player (for Set ELO)
  const [eloInputs, setEloInputs] = useState<Record<number, SetEloInputs>>({})

  const { data, isLoading, isError, refetch, isFetching } = useFlaggedPlayers()

  const closePanel = (playerId: number) => setActivePanel((p) => ({ ...p, [playerId]: null }))
  const networkError = () => messageApi.error('Network error — check backend logs')

  const fetchStatsMutation = useFetchPlayerStats({
    onSuccess: (result, playerId) => {
      if (result.success) {
        messageApi.success(`${result.playerName}: found ${result.matchesFound} matches — stats saved`)
        closePanel(playerId)
      } else {
        messageApi.error(result.error ?? 'Stats fetch failed')
      }
    },
    onError: networkError,
  })

  const fetchEloMutation = useFetchPlayerElo({
    onSuccess: (result, playerId) => {
      if (result.success) {
        messageApi.success(`${result.playerName}: ELO ${result.elo?.toFixed(0)} fetched from TennisAbstract`)
        closePanel(playerId)
      } else {
        messageApi.error(result.error ?? 'ELO fetch failed')
      }
    },
    onError: networkError,
  })

  const setEloMutation = useSetPlayerElo({
    onSuccess: (result, playerId) => {
      messageApi.success(`ELO saved for ${result.playerName}`)
      closePanel(playerId)
    },
    onError: networkError,
  })

  function togglePanel(playerId: number, panel: AdminPanel) {
    setActivePanel((prev) => ({
      ...prev,
      [playerId]: prev[playerId] === panel ? null : panel,
    }))
  }

  function getSlugInput(player: FlaggedPlayer): string {
    if (slugInputs[player.playerId] !== undefined) return slugInputs[player.playerId]
    return player.taSlug ?? player.autoSlug
  }

  function getEloInput(playerId: number) {
    return eloInputs[playerId] ?? EMPTY_ELO_INPUTS
  }

  function getEloNameInput(player: FlaggedPlayer): string {
    if (eloNameInputs[player.playerId] !== undefined) return eloNameInputs[player.playerId]
    return player.playerName
  }

  const columns: ColumnsType<FlaggedPlayer> = [
    {
      title: 'Player',
      dataIndex: 'playerName',
      key: 'player',
      render: (name: string, record) => {
        const tint = tourColor(record.tour)
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontFamily: 'var(--font-body)',
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--text-primary)',
            }}>
              {name}
            </span>
            <span style={{
              fontFamily: 'var(--font-display)',
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: tint,
              background: withAlpha(tint, 0.094),
              border: `1px solid ${withAlpha(tint, 0.208)}`,
              borderRadius: 3,
              padding: '1px 6px',
            }}>
              {record.tour}
            </span>
          </div>
        )
      },
    },
    {
      title: 'Flags',
      dataIndex: 'flags',
      key: 'flags',
      render: (flags: string[], record) => (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {flags.map((f) => <FlagPill key={f} flag={f} />)}
          </div>
          <SurfaceGapNote missingSurfaces={record.missingSurfaces} />
        </>
      ),
    },
    {
      title: 'ELO',
      dataIndex: 'hasElo',
      key: 'hasElo',
      width: 70,
      render: (v: boolean) => <StatusDot ok={v} />,
    },
    {
      title: 'Stats',
      dataIndex: 'hasStats',
      key: 'hasStats',
      width: 70,
      render: (v: boolean) => <StatusDot ok={v} />,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record) => (
        <AdminActions flags={record.flags} open={activePanel[record.playerId]} onToggle={panel => togglePanel(record.playerId, panel)} compact={false} />
      ),
    },
  ]

  const TOUR_ORDER: Record<string, number> = { ATP: 0, WTA: 1, CHALLENGER: 2 }
  const players = [...(data?.players ?? [])].sort(
    (a, b) => (TOUR_ORDER[a.tour] ?? 99) - (TOUR_ORDER[b.tour] ?? 99),
  )

  function renderPanel(record: FlaggedPlayer, compact: boolean) {
    const playerId = record.playerId
    const panel = activePanel[playerId]
    if (panel === 'stats') {
      const slug = getSlugInput(record)
      return <FixStatsPanel player={record} value={slug} compact={compact}
        onChange={value => setSlugInputs((s) => ({ ...s, [playerId]: value }))}
        onSubmit={() => fetchStatsMutation.mutate({ playerId, payload: fixStatsPayload(slug) })}
        loading={fetchStatsMutation.isPending && fetchStatsMutation.variables?.playerId === playerId} />
    }
    if (panel === 'fetch-elo') {
      const taName = getEloNameInput(record)
      return <FetchEloPanel player={record} value={taName} compact={compact}
        onChange={value => setEloNameInputs((s) => ({ ...s, [playerId]: value }))}
        onSubmit={() => fetchEloMutation.mutate({ playerId, payload: fetchEloPayload(taName, record.playerName) })}
        loading={fetchEloMutation.isPending && fetchEloMutation.variables?.playerId === playerId} />
    }
    if (panel === 'set-elo') {
      const inputs = getEloInput(playerId)
      return <SetEloPanel player={record} inputs={inputs} compact={compact}
        onChange={(key, value) => setEloInputs((s) => ({ ...s, [playerId]: { ...getEloInput(playerId), [key]: value } }))}
        onSubmit={() => {
          const payload = buildSetEloPayload(inputs)
          if (payload) setEloMutation.mutate({ playerId, payload })
        }}
        loading={setEloMutation.isPending && setEloMutation.variables?.playerId === playerId} />
    }
    return null
  }

  return (
    <>
      {contextHolder}
      <div className="page-shell">
        <div className="page-container" style={{ maxWidth: 980 }}>

          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32, gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: 12,
                letterSpacing: '0.18em',
                textTransform: 'uppercase',
                color: 'var(--text-secondary)',
                marginBottom: 6,
                fontWeight: 600,
              }}>
                Admin · Data Quality
              </div>
              <h1 style={{
                fontFamily: 'var(--font-display)',
                fontSize: isMobile ? 26 : 32,
                fontWeight: 800,
                letterSpacing: '0.03em',
                color: 'var(--text-primary)',
                margin: 0,
                textTransform: 'uppercase',
                lineHeight: 1.1,
              }}>
                Flagged Players
              </h1>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                color: 'var(--text-secondary)',
                margin: '8px 0 0',
              }}>
                Players from today's and tomorrow's matches with missing ELO or rolling stats
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <Button onClick={() => refetch()} loading={isFetching}>
                Refresh
              </Button>
              {onSignOut && <Button onClick={onSignOut}>Sign out</Button>}
            </div>
          </div>

          {/* Props pipeline health — unlinked props silently lose their
              side, so the board can only show them as missing. */}
          <PropsAuditBanner />

          {/* Error */}
          {isError && (
            <div style={{
              padding: '16px 18px',
              background: 'var(--negative-soft)',
              border: '1px solid color-mix(in srgb, var(--negative) 30%, transparent)',
              borderRadius: 8,
              color: 'var(--negative)',
              fontFamily: 'var(--font-body)',
              fontSize: 13,
              marginBottom: 24,
            }}>
              Failed to load flagged players. Is the backend running?
            </div>
          )}

          {/* Empty state */}
          {!isLoading && !isError && players.length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '72px 0',
              fontFamily: 'var(--font-body)',
              color: 'var(--text-secondary)',
              fontSize: 15,
            }}>
              No flagged players — all predictions have complete data.
            </div>
          )}

          {/* Table */}
          {(isLoading || players.length > 0) && (
            isMobile ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {players.map((record) => (
                  <div
                    key={record.playerId}
                    style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-card)',
                      borderRadius: 10,
                      padding: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{record.playerName}</div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {record.flags.map((f) => <FlagPill key={f} flag={f} />)}
                      </div>
                    </div>
                    <SurfaceGapNote missingSurfaces={record.missingSurfaces} />
                    <AdminActions flags={record.flags} open={activePanel[record.playerId]} onToggle={panel => togglePanel(record.playerId, panel)} compact />
                    {renderPanel(record, true)}
                  </div>
                ))}
              </div>
            ) : (
              <Table
                dataSource={players}
                columns={columns}
                rowKey="playerId"
                loading={isLoading}
                pagination={false}
                expandable={{
                  expandedRowKeys: players
                    .filter((p) => activePanel[p.playerId] != null)
                    .map((p) => p.playerId),
                  expandedRowRender: (record) => renderPanel(record, false),
                  rowExpandable: (record) => activePanel[record.playerId] !== null && activePanel[record.playerId] !== undefined,
                  showExpandColumn: false,
                }}
                style={{
                  background: 'var(--bg-card)',
                  borderRadius: 10,
                }}
              />
            )
          )}
        </div>
      </div>
    </>
  )
}
