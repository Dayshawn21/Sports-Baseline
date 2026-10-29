import { useEffect, useState } from 'react'
import {
  Button,
  Input,
  InputNumber,
  Table,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchFlaggedPlayers, fetchPlayerElo, fetchPlayerStats, setPlayerElo } from '~/api/admin'
import type { FlaggedPlayer, FetchEloRequest, FetchStatsRequest, SetEloRequest } from '~/types/admin'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useAdminSession } from '~/hooks/useAdmin'
import AdminSignIn from '~/components/admin/AdminSignIn'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { sessionAdminKey } from '~/utils/adminAuth'
import { httpStatus, retryAfterSeconds } from '~/utils/httpError'
import PropsAuditBanner from '~/components/tennis/PropsAuditBanner'
import { withAlpha } from '~/utils/color'

const TOUR_COLORS: Record<string, string> = {
  ATP: 'var(--atp-blue)',
  WTA: 'var(--wta-pink)',
}

const FLAG_META: Record<string, { color: string; bg: string; border: string }> = {
  elo_missing:         { color: 'var(--negative)', bg: 'var(--negative-soft)',    border: 'color-mix(in srgb, var(--negative) 30%, transparent)' },
  p1_elo_missing:      { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
  p2_elo_missing:      { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
  ml_features_partial: { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
  high_overround:      { color: 'var(--caution)', bg: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
}

function FlagPill({ flag }: { flag: string }) {
  const meta = FLAG_META[flag] ?? { color: 'var(--text-secondary)', bg: 'var(--border-card)', border: 'var(--border-card)' }
  return (
    <span style={{
      fontFamily: 'var(--font-display)',
      fontSize: 10,
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

type ActivePanel = 'stats' | 'fetch-elo' | 'set-elo' | null

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
  const qc = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()

  // Which panel is open per player: playerId → 'stats' | 'elo' | null
  const [activePanel, setActivePanel] = useState<Record<number, ActivePanel>>({})
  // Slug input per player (for Fix Stats)
  const [slugInputs, setSlugInputs] = useState<Record<number, string>>({})
  // Name input per player (for Fetch ELO)
  const [eloNameInputs, setEloNameInputs] = useState<Record<number, string>>({})
  // Manual ELO inputs per player (for Set ELO)
  const [eloInputs, setEloInputs] = useState<Record<number, {
    elo: string; hard: string; clay: string; grass: string
  }>>({})

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['admin', 'flagged'],
    queryFn: fetchFlaggedPlayers,
    staleTime: 60 * 1000,
  })

  const fetchStatsMutation = useMutation({
    mutationFn: ({ playerId, payload }: { playerId: number; payload: FetchStatsRequest }) =>
      fetchPlayerStats(playerId, payload),
    onSuccess: (result, { playerId }) => {
      if (result.success) {
        messageApi.success(`${result.playerName}: found ${result.matchesFound} matches — stats saved`)
        setActivePanel((p) => ({ ...p, [playerId]: null }))
        qc.invalidateQueries({ queryKey: ['admin', 'flagged'] })
      } else {
        messageApi.error(result.error ?? 'Stats fetch failed')
      }
    },
    onError: () => messageApi.error('Network error — check backend logs'),
  })

  const fetchEloMutation = useMutation({
    mutationFn: ({ playerId, payload }: { playerId: number; payload: FetchEloRequest }) =>
      fetchPlayerElo(playerId, payload),
    onSuccess: (result, { playerId }) => {
      if (result.success) {
        messageApi.success(`${result.playerName}: ELO ${result.elo?.toFixed(0)} fetched from TennisAbstract`)
        setActivePanel((p) => ({ ...p, [playerId]: null }))
        qc.invalidateQueries({ queryKey: ['admin', 'flagged'] })
      } else {
        messageApi.error(result.error ?? 'ELO fetch failed')
      }
    },
    onError: () => messageApi.error('Network error — check backend logs'),
  })

  const setEloMutation = useMutation({
    mutationFn: ({ playerId, payload }: { playerId: number; payload: SetEloRequest }) =>
      setPlayerElo(playerId, payload),
    onSuccess: (result, { playerId }) => {
      messageApi.success(`ELO saved for ${result.playerName}`)
      setActivePanel((p) => ({ ...p, [playerId]: null }))
      qc.invalidateQueries({ queryKey: ['admin', 'flagged'] })
    },
    onError: () => messageApi.error('Network error — check backend logs'),
  })

  function togglePanel(playerId: number, panel: Exclude<ActivePanel, null>) {
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
    return eloInputs[playerId] ?? { elo: '', hard: '', clay: '', grass: '' }
  }

  function getEloNameInput(player: FlaggedPlayer): string {
    if (eloNameInputs[player.playerId] !== undefined) return eloNameInputs[player.playerId]
    return player.playerName
  }

  const hasEloFlag = (flags: string[]) =>
    flags.some((f) => f === 'elo_missing' || f === 'p1_elo_missing' || f === 'p2_elo_missing')
  const hasStatsFlag = (flags: string[]) => flags.includes('ml_features_partial')

  const columns: ColumnsType<FlaggedPlayer> = [
    {
      title: 'Player',
      dataIndex: 'playerName',
      key: 'player',
      render: (name: string, record) => {
        const tourColor = TOUR_COLORS[record.tour] ?? 'var(--text-secondary)'
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
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: tourColor,
              background: withAlpha(tourColor, 0.094),
              border: `1px solid ${withAlpha(tourColor, 0.208)}`,
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
      render: (flags: string[]) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {flags.map((f) => <FlagPill key={f} flag={f} />)}
        </div>
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
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {hasStatsFlag(record.flags) && (
            <Button
              size="small"
              type={activePanel[record.playerId] === 'stats' ? 'primary' : 'default'}
              onClick={() => togglePanel(record.playerId, 'stats')}
              style={{ fontSize: 12 }}
            >
              Fix Stats
            </Button>
          )}
          {hasEloFlag(record.flags) && (
            <Button
              size="small"
              type={activePanel[record.playerId] === 'fetch-elo' ? 'primary' : 'default'}
              onClick={() => togglePanel(record.playerId, 'fetch-elo')}
              style={{ fontSize: 12 }}
            >
              Fetch ELO
            </Button>
          )}
          {hasEloFlag(record.flags) && (
            <Button
              size="small"
              type={activePanel[record.playerId] === 'set-elo' ? 'primary' : 'default'}
              onClick={() => togglePanel(record.playerId, 'set-elo')}
              style={{ fontSize: 12 }}
            >
              Set ELO
            </Button>
          )}
        </div>
      ),
    },
  ]

  const TOUR_ORDER: Record<string, number> = { ATP: 0, WTA: 1, CHALLENGER: 2 }
  const players = [...(data?.players ?? [])].sort(
    (a, b) => (TOUR_ORDER[a.tour] ?? 99) - (TOUR_ORDER[b.tour] ?? 99),
  )

  function renderMobilePanel(record: FlaggedPlayer) {
    const panel = activePanel[record.playerId]
    if (!panel) return null

    if (panel === 'stats') {
      const slug = getSlugInput(record)
      const loading = fetchStatsMutation.isPending && fetchStatsMutation.variables?.playerId === record.playerId
      return (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Input
            value={slug}
            onChange={(e) => setSlugInputs((s) => ({ ...s, [record.playerId]: e.target.value }))}
            placeholder={record.autoSlug}
            style={{ width: '100%', fontFamily: 'var(--font-mono)', fontSize: 13 }}
            onPressEnter={() => fetchStatsMutation.mutate({ playerId: record.playerId, payload: { taSlug: slug || null } })}
          />
          <Button
            type="primary"
            loading={loading}
            onClick={() => fetchStatsMutation.mutate({ playerId: record.playerId, payload: { taSlug: slug || null } })}
          >
            Fetch Stats
          </Button>
        </div>
      )
    }

    if (panel === 'fetch-elo') {
      const taName = getEloNameInput(record)
      const loading = fetchEloMutation.isPending && fetchEloMutation.variables?.playerId === record.playerId
      return (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Input
            value={taName}
            onChange={(e) => setEloNameInputs((s) => ({ ...s, [record.playerId]: e.target.value }))}
            placeholder={record.playerName}
            style={{ width: '100%', fontFamily: 'var(--font-body)', fontSize: 13 }}
            onPressEnter={() => fetchEloMutation.mutate({
              playerId: record.playerId,
              payload: { taName: taName !== record.playerName ? taName : null },
            })}
          />
          <Button
            type="primary"
            loading={loading}
            onClick={() => fetchEloMutation.mutate({
              playerId: record.playerId,
              payload: { taName: taName !== record.playerName ? taName : null },
            })}
          >
            Fetch ELO
          </Button>
        </div>
      )
    }

    const inputs = getEloInput(record.playerId)
    const loading = setEloMutation.isPending && setEloMutation.variables?.playerId === record.playerId
    return (
      <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 8 }}>
        {([
          { key: 'elo', label: 'Overall*' },
          { key: 'hard', label: 'Hard' },
          { key: 'clay', label: 'Clay' },
          { key: 'grass', label: 'Grass' },
        ] as const).map(({ key, label }) => (
          <div key={key}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
            <InputNumber
              value={inputs[key] ? Number(inputs[key]) : undefined}
              onChange={(v) => setEloInputs((s) => ({
                ...s,
                [record.playerId]: { ...getEloInput(record.playerId), [key]: String(v ?? '') },
              }))}
              placeholder={key === 'elo' ? '1500' : 'optional'}
              min={500}
              max={3000}
              step={10}
              style={{ width: '100%' }}
            />
          </div>
        ))}
        <Button
          type="primary"
          loading={loading}
          disabled={!inputs.elo}
          onClick={() => {
            const elo = Number(inputs.elo)
            if (!elo) return
            const payload: SetEloRequest = {
              elo,
              eloHard: inputs.hard ? Number(inputs.hard) : null,
              eloClay: inputs.clay ? Number(inputs.clay) : null,
              eloGrass: inputs.grass ? Number(inputs.grass) : null,
            }
            setEloMutation.mutate({ playerId: record.playerId, payload })
          }}
          style={{ gridColumn: '1 / -1' }}
        >
          Save ELO
        </Button>
      </div>
    )
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
                    <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {hasStatsFlag(record.flags) && (
                        <Button size="small" type={activePanel[record.playerId] === 'stats' ? 'primary' : 'default'} onClick={() => togglePanel(record.playerId, 'stats')}>Fix Stats</Button>
                      )}
                      {hasEloFlag(record.flags) && (
                        <Button size="small" type={activePanel[record.playerId] === 'fetch-elo' ? 'primary' : 'default'} onClick={() => togglePanel(record.playerId, 'fetch-elo')}>Fetch ELO</Button>
                      )}
                      {hasEloFlag(record.flags) && (
                        <Button size="small" type={activePanel[record.playerId] === 'set-elo' ? 'primary' : 'default'} onClick={() => togglePanel(record.playerId, 'set-elo')}>Set ELO</Button>
                      )}
                    </div>
                    {renderMobilePanel(record)}
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
                  expandedRowRender: (record) => {
                  const panel = activePanel[record.playerId]

                  if (panel === 'stats') {
                    const slug = getSlugInput(record)
                    const isLoading = fetchStatsMutation.isPending &&
                      fetchStatsMutation.variables?.playerId === record.playerId

                    return (
                      <div style={{
                        padding: '16px 18px',
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid var(--border-card)',
                        borderRadius: 8,
                        margin: '4px 0 8px',
                      }}>
                        <div style={{
                          fontFamily: 'var(--font-display)',
                          fontSize: 11,
                          fontWeight: 700,
                          letterSpacing: '0.1em',
                          textTransform: 'uppercase',
                          color: 'var(--text-primary)',
                          marginBottom: 12,
                        }}>
                          Fix Rolling Stats — {record.playerName}
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          <div style={{
                            fontFamily: 'var(--font-body)',
                            fontSize: 12,
                            color: 'var(--text-secondary)',
                            marginBottom: 6,
                          }}>
                            TennisAbstract Slug
                            <span style={{ color: 'var(--text-muted)', marginLeft: 8, fontStyle: 'italic' }}>
                              (auto: {record.autoSlug}{record.taSlug ? ` · saved: ${record.taSlug}` : ''})
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <Input
                              value={slug}
                              onChange={(e) => setSlugInputs((s) => ({ ...s, [record.playerId]: e.target.value }))}
                              placeholder={record.autoSlug}
                              style={{ maxWidth: 280, fontFamily: 'var(--font-mono)', fontSize: 13 }}
                              onPressEnter={() => {
                                fetchStatsMutation.mutate({
                                  playerId: record.playerId,
                                  payload: { taSlug: slug || null },
                                })
                              }}
                            />
                            <Button
                              type="primary"
                              loading={isLoading}
                              onClick={() => {
                                fetchStatsMutation.mutate({
                                  playerId: record.playerId,
                                  payload: { taSlug: slug || null },
                                })
                              }}
                            >
                              Fetch Stats
                            </Button>
                          </div>
                        </div>
                        <div style={{
                          fontFamily: 'var(--font-body)',
                          fontSize: 11,
                          color: 'var(--text-muted)',
                          marginTop: 6,
                        }}>
                          The slug is saved to the DB and used for future ingests. Leave unchanged to use the auto-generated slug.
                        </div>
                      </div>
                    )
                  }

                  if (panel === 'fetch-elo') {
                    const taName = getEloNameInput(record)
                    const isLoading = fetchEloMutation.isPending &&
                      fetchEloMutation.variables?.playerId === record.playerId
                    // No Challenger ELO page exists — the backend searches both
                    // tables, since that label covers men's Challengers and WTA 125.
                    const eloTables = record.tour?.toUpperCase() === 'CHALLENGER'
                      ? 'ATP/WTA'
                      : record.tour

                    return (
                      <div style={{
                        padding: '16px 18px',
                        background: 'var(--negative-soft)',
                        border: '1px solid color-mix(in srgb, var(--negative) 30%, transparent)',
                        borderRadius: 8,
                        margin: '4px 0 8px',
                      }}>
                        <div style={{
                          fontFamily: 'var(--font-display)',
                          fontSize: 11,
                          fontWeight: 700,
                          letterSpacing: '0.1em',
                          textTransform: 'uppercase',
                          color: 'var(--negative)',
                          marginBottom: 12,
                        }}>
                          Fetch ELO from TennisAbstract — {record.playerName}
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          <div style={{
                            fontFamily: 'var(--font-body)',
                            fontSize: 12,
                            color: 'var(--text-secondary)',
                            marginBottom: 6,
                          }}>
                            TennisAbstract Name
                            <span style={{ color: 'var(--text-muted)', marginLeft: 8, fontStyle: 'italic' }}>
                              (edit if spelling differs from our DB)
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <Input
                              value={taName}
                              onChange={(e) => setEloNameInputs((s) => ({ ...s, [record.playerId]: e.target.value }))}
                              placeholder={record.playerName}
                              style={{ maxWidth: 280, fontFamily: 'var(--font-body)', fontSize: 13 }}
                              onPressEnter={() => {
                                fetchEloMutation.mutate({
                                  playerId: record.playerId,
                                  payload: { taName: taName !== record.playerName ? taName : null },
                                })
                              }}
                            />
                            <Button
                              type="primary"
                              loading={isLoading}
                              onClick={() => {
                                fetchEloMutation.mutate({
                                  playerId: record.playerId,
                                  payload: { taName: taName !== record.playerName ? taName : null },
                                })
                              }}
                            >
                              Fetch ELO
                            </Button>
                          </div>
                        </div>
                        <div style={{
                          fontFamily: 'var(--font-body)',
                          fontSize: 11,
                          color: 'var(--text-muted)',
                          marginTop: 6,
                        }}>
                          Searches TennisAbstract's {eloTables} ELO ratings table for this name. If found, Hard/Clay/Grass ELO are also saved.
                        </div>
                      </div>
                    )
                  }

                  if (panel === 'set-elo') {
                    const inputs = getEloInput(record.playerId)
                    const isLoading = setEloMutation.isPending &&
                      setEloMutation.variables?.playerId === record.playerId

                    return (
                      <div style={{
                        padding: '16px 18px',
                        background: 'var(--negative-soft)',
                        border: '1px solid color-mix(in srgb, var(--negative) 30%, transparent)',
                        borderRadius: 8,
                        margin: '4px 0 8px',
                      }}>
                        <div style={{
                          fontFamily: 'var(--font-display)',
                          fontSize: 11,
                          fontWeight: 700,
                          letterSpacing: '0.1em',
                          textTransform: 'uppercase',
                          color: 'var(--negative)',
                          marginBottom: 12,
                        }}>
                          Set ELO Manually — {record.playerName}
                        </div>
                        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                          {([
                            { key: 'elo',   label: 'Overall ELO', required: true  },
                            { key: 'hard',  label: 'Hard ELO',    required: false },
                            { key: 'clay',  label: 'Clay ELO',    required: false },
                            { key: 'grass', label: 'Grass ELO',   required: false },
                          ] as const).map(({ key, label, required }) => (
                            <div key={key}>
                              <div style={{
                                fontFamily: 'var(--font-body)',
                                fontSize: 12,
                                color: required ? 'var(--text-secondary)' : 'var(--text-muted)',
                                marginBottom: 4,
                              }}>
                                {label}{required && <span style={{ color: 'var(--negative)', marginLeft: 2 }}>*</span>}
                              </div>
                              <InputNumber
                                value={inputs[key] ? Number(inputs[key]) : undefined}
                                onChange={(v) => setEloInputs((s) => ({
                                  ...s,
                                  [record.playerId]: { ...getEloInput(record.playerId), [key]: String(v ?? '') },
                                }))}
                                placeholder={key === 'elo' ? '1500' : 'optional'}
                                min={500}
                                max={3000}
                                step={10}
                                style={{ width: 120 }}
                              />
                            </div>
                          ))}
                          <Button
                            type="primary"
                            loading={isLoading}
                            disabled={!inputs.elo}
                            onClick={() => {
                              const elo = Number(inputs.elo)
                              if (!elo) return
                              const payload: SetEloRequest = {
                                elo,
                                eloHard:  inputs.hard  ? Number(inputs.hard)  : null,
                                eloClay:  inputs.clay  ? Number(inputs.clay)  : null,
                                eloGrass: inputs.grass ? Number(inputs.grass) : null,
                              }
                              setEloMutation.mutate({ playerId: record.playerId, payload })
                            }}
                          >
                            Save ELO
                          </Button>
                        </div>
                        <div style={{
                          fontFamily: 'var(--font-body)',
                          fontSize: 11,
                          color: 'var(--text-muted)',
                          marginTop: 10,
                        }}>
                          Typical ATP/WTA range: 1300–2100. Qualifiers are often 1300–1500.
                        </div>
                      </div>
                    )
                  }

                  return null
                  },
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
